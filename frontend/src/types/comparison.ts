// 注意：后端使用 _CAMEL_CONFIG，API JSON 字段名为 camelCase

export interface SupplierPrice {
  supplierFileId: string;
  supplierName: string;
  unitPrice: number | null;
  totalPrice: number | null;
  taxBasis?: string | null;
  unit?: string | null;
  complianceStatus?: string | null;
  isAcceptable?: boolean | null;
}

export interface AnomalyDetail {
  type: 'tax_basis_mismatch' | 'unit_mismatch' | 'currency_mismatch' | 'missing_required_field';
  description: string;
  blocking: boolean;
  affectedSuppliers: string[];
}

export interface ComparisonResult {
  id: string;
  groupId: string;
  groupName: string;
  projectId: string;
  comparisonStatus: 'comparable' | 'blocked' | 'partial';
  supplierPrices: SupplierPrice[];
  minPrice: number | null;
  effectiveMinPrice: number | null;
  maxPrice: number | null;
  avgPrice: number | null;
  priceDiff: number | null;
  hasAnomaly: boolean;
  anomalyDetails: AnomalyDetail[];
  missingSuppliers: string[];
  generatedAt: string;
}

export interface ExportResult {
  filePath: string;
  fileName: string;
  sheetCount: number;
}
