/**
 * mcp-fiscal-brasil Node.js wrapper.
 *
 * Wraps the Python CLI (`mcp-fiscal`) as subprocess and returns parsed JSON.
 * Requires `mcp-fiscal-brasil` Python package installed (pipx / uv tool / pip).
 *
 * Usage:
 *   import { lookupCNPJ, analyzeCompliance, compareRegimes } from "mcp-fiscal-brasil";
 *   const cnpj = await lookupCNPJ("12345678000190");
 *   console.log(cnpj.razao_social);
 */

import { spawn } from "node:child_process";

export interface CNPJData {
  cnpj: string;
  razao_social: string;
  nome_fantasia?: string;
  situacao_cadastral: string;
  porte?: string;
  [k: string]: unknown;
}

export interface ComplianceReport {
  cnpj: string;
  razao_social: string;
  risco_geral: "baixo" | "medio" | "alto" | "critico";
  score: number;
  achados: Array<Record<string, unknown>>;
  resumo_executivo: string;
  fontes_consultadas: string[];
}

export interface RegimesComparison {
  cenario_faturamento_anual: number;
  cenario_setor: string;
  melhor_opcao: string;
  economia_anual_vs_pior: number;
  opcoes: Array<Record<string, unknown>>;
  observacoes: string;
}

export class MCPFiscalError extends Error {
  constructor(message: string, public exitCode: number, public stderr: string) {
    super(message);
    this.name = "MCPFiscalError";
  }
}

function runCli(args: string[]): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const proc = spawn("mcp-fiscal", [...args, "--json"], {
      stdio: ["ignore", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";
    proc.stdout.on("data", (chunk) => (stdout += chunk.toString()));
    proc.stderr.on("data", (chunk) => (stderr += chunk.toString()));

    proc.on("error", (err) =>
      reject(new MCPFiscalError(`Failed to spawn mcp-fiscal: ${err.message}`, -1, "")),
    );

    proc.on("close", (code) => {
      if (code !== 0) {
        reject(
          new MCPFiscalError(
            `mcp-fiscal exited with code ${code}: ${stderr.trim()}`,
            code ?? -1,
            stderr,
          ),
        );
        return;
      }
      try {
        resolve(JSON.parse(stdout));
      } catch {
        reject(new MCPFiscalError(`Failed to parse JSON output: ${stdout}`, 0, ""));
      }
    });
  });
}

/** Consulta dados cadastrais de um CNPJ. */
export async function lookupCNPJ(cnpj: string): Promise<CNPJData> {
  return runCli(["cnpj", cnpj]) as Promise<CNPJData>;
}

/** Valida CPF brasileiro (offline). */
export async function validateCPF(cpf: string): Promise<Record<string, unknown>> {
  return runCli(["cpf", cpf]) as Promise<Record<string, unknown>>;
}

/** Consulta endereco pelo CEP. */
export async function lookupCEP(cep: string): Promise<Record<string, unknown>> {
  return runCli(["cep", cep]) as Promise<Record<string, unknown>>;
}

/** Analise consolidada de compliance fiscal de um CNPJ. */
export async function analyzeCompliance(cnpj: string): Promise<ComplianceReport> {
  return runCli(["compliance", cnpj]) as Promise<ComplianceReport>;
}

/** Score de risco para due diligence de fornecedor. */
export async function scoreSupplier(
  cnpj: string,
  options: { estrito?: boolean } = {},
): Promise<Record<string, unknown>> {
  const args = ["supplier", cnpj];
  if (options.estrito) args.push("--estrito");
  return runCli(args) as Promise<Record<string, unknown>>;
}

/** Compara regimes tributarios. */
export async function compareRegimes(params: {
  faturamento: number;
  setor: "comercio" | "servicos" | "industria";
  folha?: number;
}): Promise<RegimesComparison> {
  const args = [
    "regimes",
    "--faturamento",
    String(params.faturamento),
    "--setor",
    params.setor,
  ];
  if (params.folha !== undefined) {
    args.push("--folha", String(params.folha));
  }
  return runCli(args) as Promise<RegimesComparison>;
}
