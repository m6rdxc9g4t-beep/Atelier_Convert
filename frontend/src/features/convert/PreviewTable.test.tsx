import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Column } from "../../types/convert";
import { PreviewTable, swapEdits } from "./PreviewTable";

const COLUMNS: Column[] = [
  { key: "date", label: "Date", type: "date", include: true, role: "date" },
  { key: "libelle", label: "Libellé", type: "text", include: true, role: "label" },
  { key: "montant", label: "Montant", type: "currency", include: true, role: "amount" },
];
const ROWS = [
  { date: "2026-03-02", libelle: "EDF", montant: -84.2 },
  { date: "2026-03-04", libelle: "Salaire", montant: "n/a" },
];

describe("aperçu de la table", () => {
  it("affiche les valeurs à la française et signale les valeurs non converties", () => {
    render(<PreviewTable columns={COLUMNS} rows={ROWS} total={2} busy={false} onColumns={vi.fn()} onMore={null} />);
    const body = screen.getAllByRole("row");
    expect(within(body[1]!).getByText("02/03/2026")).toBeInTheDocument();
    expect(within(body[1]!).getByText(/-84,20/)).toHaveClass("text-negative");
    expect(within(body[2]!).getByText("n/a")).toHaveAttribute("title", expect.stringContaining("gardée telle quelle"));
    expect(screen.getByText(/1 valeur\(s\) non converties/)).toBeInTheDocument();
  });

  it("renomme, écarte, change le type et déplace une colonne", async () => {
    const onColumns = vi.fn();
    render(<PreviewTable columns={COLUMNS} rows={ROWS} total={2} busy={false} onColumns={onColumns} onMore={null} />);
    const name = screen.getByRole("textbox", { name: "Nom de la colonne Libellé" });
    await userEvent.clear(name);
    await userEvent.type(name, "Opération{Enter}");
    expect(onColumns).toHaveBeenLastCalledWith([COLUMNS[0], { ...COLUMNS[1], label: "Opération" }, COLUMNS[2]]);

    await userEvent.click(screen.getByRole("checkbox", { name: "Inclure la colonne Date" }));
    expect(onColumns).toHaveBeenLastCalledWith([{ ...COLUMNS[0], include: false }, COLUMNS[1], COLUMNS[2]]);

    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Type de la colonne Montant" }), "text");
    expect(onColumns).toHaveBeenLastCalledWith([COLUMNS[0], COLUMNS[1], { ...COLUMNS[2], type: "text" }]);

    await userEvent.click(screen.getByRole("button", { name: "Déplacer Montant à gauche" }));
    expect(onColumns).toHaveBeenLastCalledWith([COLUMNS[0], COLUMNS[2], COLUMNS[1]]);
    expect(screen.getByRole("button", { name: "Déplacer Date à gauche" })).toBeDisabled();
  });

  it("un nom vidé revient à l'ancien, sans enregistrement", async () => {
    const onColumns = vi.fn();
    render(<PreviewTable columns={COLUMNS} rows={ROWS} total={2} busy={false} onColumns={onColumns} onMore={null} />);
    const name = screen.getByRole("textbox", { name: "Nom de la colonne Date" });
    await userEvent.clear(name);
    await userEvent.tab();
    expect(onColumns).not.toHaveBeenCalled();
    expect(name).toHaveValue("Date");
  });

  it("propose d'afficher plus de lignes", async () => {
    const onMore = vi.fn();
    render(<PreviewTable columns={COLUMNS} rows={ROWS} total={600} busy={false} onColumns={vi.fn()} onMore={onMore} />);
    await userEvent.click(screen.getByRole("button", { name: "Afficher plus de lignes" }));
    expect(onMore).toHaveBeenCalled();
  });

  it("corrige un libellé au double-clic et passe à la ligne suivante avec Entrée", async () => {
    const onCells = vi.fn().mockResolvedValue(true);
    render(<PreviewTable columns={COLUMNS} rows={ROWS} total={2} busy={false} onColumns={vi.fn()} onCells={onCells} onMore={null} />);
    await userEvent.dblClick(screen.getByText("EDF"));
    const input = screen.getByRole("textbox", { name: "Corriger Libellé, ligne 1" });
    expect(input).toHaveValue("EDF");
    await userEvent.clear(input);
    await userEvent.type(input, "Électricité EDF{Enter}");
    expect(onCells).toHaveBeenCalledWith([{ row: 0, key: "libelle", value: "Électricité EDF" }]);
    expect(screen.queryByRole("textbox", { name: /Corriger/ })).not.toBeInTheDocument();
  });

  it("au clavier : flèches, Entrée pour corriger, Échap pour annuler ; rien n'est envoyé sans changement", async () => {
    const onCells = vi.fn().mockResolvedValue(true);
    render(<PreviewTable columns={COLUMNS} rows={ROWS} total={2} busy={false} onColumns={vi.fn()} onCells={onCells} onMore={null} />);
    const first = screen.getByRole("cell", { name: "Date, ligne 1 : 02/03/2026" });
    first.focus();
    await userEvent.keyboard("{ArrowRight}{ArrowRight}{Enter}");
    const amount = screen.getByRole("textbox", { name: "Corriger Montant, ligne 1" });
    expect(amount).toHaveValue("-84,2");
    await userEvent.keyboard("{Escape}");
    expect(amount).not.toBeInTheDocument();
    await userEvent.keyboard("{Enter}{Enter}");
    expect(onCells).not.toHaveBeenCalled();
  });

  it("une saisie refusée reste ouverte ; une cellule corrigée montre la valeur lue", async () => {
    const onCells = vi.fn().mockResolvedValue(false);
    const edited = { "0:libelle": "PRLV EDF" };
    render(<PreviewTable columns={COLUMNS} rows={ROWS} total={2} busy={false} edited={edited} onColumns={vi.fn()} onCells={onCells} onMore={null} />);
    expect(screen.getByText("EDF")).toHaveAttribute("title", "Corrigé — lu dans le fichier : PRLV EDF");
    expect(screen.getByText("EDF")).toHaveClass("cell-edited");
    expect(screen.getByText(/1 cellule\(s\) corrigée\(s\)/)).toBeInTheDocument();
    await userEvent.dblClick(screen.getByText("02/03/2026"));
    const input = screen.getByRole("textbox", { name: "Corriger Date, ligne 1" });
    await userEvent.clear(input);
    await userEvent.type(input, "demain{Enter}");
    expect(onCells).toHaveBeenCalledWith([{ row: 0, key: "date", value: "demain" }]);
    expect(input).toBeInTheDocument();
  });

  it("inverse débit et crédit d'une ligne de relevé", async () => {
    const columns: Column[] = [
      { key: "libelle", label: "Libellé", type: "text", include: true, role: "label" },
      { key: "debit", label: "Débit", type: "currency", include: true, role: "debit" },
      { key: "credit", label: "Crédit", type: "currency", include: true, role: "credit" },
    ];
    const rows = [{ libelle: "Virement interne reçu", debit: 21.73, credit: null }];
    expect(swapEdits(rows[0]!, 0, columns)).toEqual([
      { row: 0, key: "debit", value: null },
      { row: 0, key: "credit", value: 21.73 },
    ]);
    expect(swapEdits({ libelle: "x", debit: null, credit: null }, 0, columns)).toBeNull();
    expect(swapEdits(rows[0]!, 0, COLUMNS)).toBeNull();
    const onCells = vi.fn().mockResolvedValue(true);
    render(<PreviewTable columns={columns} rows={rows} total={1} busy={false} onColumns={vi.fn()} onCells={onCells} onMore={null} />);
    await userEvent.click(screen.getByRole("button", { name: "Ligne 1 : passer en crédit" }));
    expect(onCells).toHaveBeenCalledWith(swapEdits(rows[0]!, 0, columns));
  });
});
