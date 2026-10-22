import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Column } from "../../types/convert";
import { PreviewTable } from "./PreviewTable";

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
});
