/** 供应商文件（对应 SupplierFileResponse） */
export interface SupplierFile {
  id: string;
  project_id: string;
  supplier_name: string;
  supplier_confirmed: boolean;
  original_filename: string;
  file_path: string;
  file_type: string;
  recognition_mode: string | null;
  imported_at: string;
}

/** 原始表格数据结构（raw_data JSON 解析后） */
export interface RawTableData {
  headers: string[];
  rows: (string | null)[][];
}

/** 原始表格（对应 RawTableResponse） */
export interface RawTable {
  id: string;
  supplier_file_id: string;
  table_index: number;
  sheet_name: string | null;
  page_number: number | null;
  row_count: number;
  column_count: number;
  raw_data: string; // JSON 字符串，需 JSON.parse 为 RawTableData
  selected: boolean;
  supplier_name?: string | null;
  original_filename?: string | null;
  supplier_confirmed?: boolean | null;
}

/** 文件上传响应（对应 FileUploadResponse） */
export interface FileUploadResponse {
  file_id: string;
  task_id: string;
  supplier_name_guess: string;
}
