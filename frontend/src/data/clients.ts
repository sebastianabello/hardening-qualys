export type Client = {
  id: string
  name: string
  empresas: string[]   // alias detectables en cabecera
}

// Ejemplo inicial (ajustar libremente)
export const CLIENTS: Client[] = [
  {
    id: "occidente",
    name: "occidente",
    empresas: []
  },
  {
    id: "fiduoccidente",
    name: "fiduoccidente",
    empresas: []
  },
  {
    id: "segurosalfa",
    name: "seguros-alfa",
    empresas: ["Contoso", "Contoso Ltd.", "CONTOSO S.A."]
  },
  {
    id: "porvenir",
    name: "porvenir",
    empresas: []
  },
  {
    id: "enlace",
    name: "enlace",
    empresas: ["CEO","PROMIGAS","GDO","PROMIGAS","PROMIPER","SURTIGAS"]
  }
]
