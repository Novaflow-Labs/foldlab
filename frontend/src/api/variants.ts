// Typed wrapper over api/client.ts for variant generation.
import { apiPost } from "./client";
import type { VariantGenerateRequest, VariantGenerateResponse } from "../types";

export function generateVariants(
  body: VariantGenerateRequest,
): Promise<VariantGenerateResponse> {
  return apiPost<VariantGenerateResponse>(`/variants/generate`, body);
}
