import config from "../../vite.config";

describe("serveur de développement (docs/SUITE.md §2)", () => {
  it("écoute sur 127.0.0.1:5176 avec un port strict et relaie /api vers FastAPI", () => {
    const server = config.server;
    expect(server?.host).toBe("127.0.0.1");
    expect(server?.port).toBe(5176);
    expect(server?.strictPort).toBe(true);
    // Host et Origin de l'interface (127.0.0.1:5176) arrivent tels quels au garde « requêtes locales » de l'API.
    expect(server?.proxy).toEqual({ "/api": { target: "http://127.0.0.1:8010", changeOrigin: false } });
  });
});
