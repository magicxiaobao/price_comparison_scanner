import { useCallback, useRef, useState } from "react";
import type { FileUploadResponse } from "../../types/file";
import { uploadFile } from "../../lib/api";

const ACCEPTED_EXTENSIONS = [".xlsx", ".docx", ".pdf"];
const ACCEPT_STRING = ".xlsx,.docx,.pdf";

interface FileUploaderProps {
  projectId: string;
  onUploadComplete: (response: FileUploadResponse, filename: string) => void;
  onError: (error: string) => void;
}

export function FileUploader({ projectId, onUploadComplete, onError }: FileUploaderProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const validateFile = (file: File): boolean => {
    const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
    if (!ACCEPTED_EXTENSIONS.includes(ext)) {
      onError(`不支持的文件类型: ${file.name}，仅支持 .xlsx、.docx、.pdf`);
      return false;
    }
    return true;
  };

  const handleUpload = useCallback(
    async (file: File) => {
      if (!validateFile(file)) return;
      setIsUploading(true);
      try {
        const resp = await uploadFile(projectId, file);
        onUploadComplete(resp, file.name);
      } catch (err: unknown) {
        const msg =
          err instanceof Error ? err.message : "上传失败";
        onError(msg);
      } finally {
        setIsUploading(false);
      }
    },
    [projectId, onUploadComplete, onError],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const files = Array.from(e.dataTransfer.files);
      for (const file of files) {
        handleUpload(file);
      }
    },
    [handleUpload],
  );

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleClick = () => {
    inputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;
    for (const file of Array.from(files)) {
      handleUpload(file);
    }
    // 重置 input 以允许重复上传同一文件
    e.target.value = "";
  };

  return (
    <div
      className={`rounded-lg border-2 border-dashed p-8 text-center transition-colors ${
        isDragging
          ? "border-blue-500 bg-blue-50"
          : "border-gray-300 bg-white hover:border-gray-400"
      } ${isUploading ? "pointer-events-none opacity-60" : "cursor-pointer"}`}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onClick={handleClick}
    >
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT_STRING}
        multiple
        className="hidden"
        onChange={handleFileChange}
      />
      {isUploading ? (
        <p className="text-gray-500">上传中...</p>
      ) : (
        <>
          <p className="text-gray-600">拖拽文件到此处，或点击选择文件</p>
          <p className="mt-1 text-sm text-gray-400">
            支持 .xlsx、.docx、.pdf 格式
          </p>
        </>
      )}
    </div>
  );
}
