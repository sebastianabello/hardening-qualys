export type Client = {
  id: string
  name: string
  empresas: string[]   // alias detectables en cabecera
}

// Ejemplo inicial (ajustar libremente)
export const CLIENTS: Client[] = [
  {
    id: "acme",
    name: "ACME",
    empresas: ["ACME", "ACME S.A.", "ACME Corp"]
  },
  {
    id: "banconia",
    name: "Banconia",
    empresas: ["Banconia", "Banconia Bank", "BANCONIA SA"]
  },
  {
    id: "contoso",
    name: "Contoso",
    empresas: ["Contoso", "Contoso Ltd.", "CONTOSO S.A."]
  },
  {
    id: "bigco",
    name: "BigCo",
    empresas: ["BigCo", "BigCo Ltd.", "BIGCO S.A."]
  }
]
