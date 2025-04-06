"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { UploadIcon, File, X, Link, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface UploadProps {
  onTaskIdUpdate?: (taskId: string) => void;
}

export function Upload({ onTaskIdUpdate }: UploadProps) {
  const router = useRouter();
  const [isDragging, setIsDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [youtubeUrl, setYoutubeUrl] = useState<string>("");
  const [activeTab, setActiveTab] = useState<string>("file");

  const uploadVideo = async () => {
    localStorage.removeItem("uploadResponse");
    if (!file) {
      setError("Please select a video file.");
      return;
    }

    const formData = new FormData();
    formData.append("video", file);

    try {
      setUploadStatus("Uploading video...");
      const response = await fetch("http://localhost:5001/upload", {
        method: "POST",
        body: formData,
      });

      if (response.ok) {
        const uploadResponse = await response.json();
        localStorage.setItem("uploadResponse", JSON.stringify(uploadResponse));
        setUploadStatus("Upload successful! Processing video...");

        // Save file to IndexedDB
        const db = await window.indexedDB.open("fileDB", 1);
        db.onsuccess = () => {
          const transaction = db.result.transaction("files", "readwrite");
          const store = transaction.objectStore("files");
          store.put(file, "uploadedFile");
        };

        const fileURL = URL.createObjectURL(file);
        localStorage.setItem("fileURL", fileURL);
        router.push(`/processing?filename=${encodeURIComponent(file.name)}`);
      } else {
        const errorData = await response.json();
        setError(errorData.error || "Upload failed. Please try again.");
      }
    } catch (error) {
      console.error("Error uploading file:", error);
      setError("Error uploading file. Please try again.");
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);

    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile?.type.startsWith("video/")) {
      setFile(droppedFile);
      setError(null);
    } else {
      setError("Please upload a video file.");
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      setError(null);
    }
  };

  const removeFile = () => {
    setFile(null);
    setError(null);
    setUploadStatus("");
  };

  const handleUpload = async (file: File) => {
    localStorage.removeItem("youtubeUrl");
    try {
      setUploading(true);
      setError(null);

      const formData = new FormData();
      formData.append("video", file);

      const response = await fetch("http://localhost:5001/upload", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Upload failed");
      }

      const data = await response.json();

      // store in indexedDB
      const db = await window.indexedDB.open("fileDB", 1);
      db.onsuccess = () => {
        const transaction = db.result.transaction("files", "readwrite");
        const store = transaction.objectStore("files");
        store.put(file, "uploadedFile");
      };

      // Store the task ID and filename for the processing page
      localStorage.setItem("taskId", data.task_id);
      localStorage.setItem("filename", file.name);

      // Create a URL for the video file
      const fileURL = URL.createObjectURL(file);
      localStorage.setItem("fileURL", fileURL);

      if (data.task_id) {
        setTaskId(data.task_id);
        if (onTaskIdUpdate) {
          onTaskIdUpdate(data.task_id);
        }
      }

      // Navigate to processing page
      router.push(`/processing?filename=${encodeURIComponent(file.name)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
      setUploading(false);
    } finally {
      setUploading(false);
    }
  };

  const handleYoutubeUrlSubmit = async () => {
    if (!youtubeUrl) {
      setError("Please enter a YouTube URL");
      return;
    }

    // Basic YouTube URL validation
    const youtubeRegex = /^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)\/.+$/;
    if (!youtubeRegex.test(youtubeUrl)) {
      setError("Please enter a valid YouTube URL");
      return;
    }

    try {
      setUploading(true);
      setError(null);
      setUploadStatus("Processing YouTube URL...");

      const response = await fetch("http://localhost:5001/youtube", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ url: youtubeUrl }),
      });

      if (!response.ok) {
        throw new Error("Failed to process YouTube URL");
      }

      const data = await response.json();

      // Store the task ID for the processing page
      localStorage.setItem("youtubeUrl", youtubeUrl);
      localStorage.setItem("taskId", data.task_id);
      localStorage.setItem("filename", "YouTube Video");

      if (data.task_id) {
        setTaskId(data.task_id);
        if (onTaskIdUpdate) {
          onTaskIdUpdate(data.task_id);
        }
      }

      // Navigate to processing page
      router.push(
        `/processing?filename=${encodeURIComponent("YouTube Video")}`
      );
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to process YouTube URL"
      );
      setUploading(false);
    } finally {
      setUploading(false);
    }
  };

  // Clean up the video URL when component unmounts
  useEffect(() => {
    return () => {
      const videoUrl = sessionStorage.getItem("videoUrl");
      if (videoUrl) {
        URL.revokeObjectURL(videoUrl);
      }
    };
  }, []);

  return (
    <div className="space-y-4">
      <Tabs defaultValue="file" className="w-full" onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="file">Upload Video</TabsTrigger>
          <TabsTrigger value="url">YouTube URL</TabsTrigger>
        </TabsList>

        <TabsContent value="file">
          <div
            className={cn(
              "border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors",
              isDragging
                ? "border-primary bg-primary/5"
                : "border-muted-foreground/25",
              file ? "bg-muted/50" : "hover:bg-muted/50"
            )}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() =>
              !file && document.getElementById("file-upload")?.click()
            }
          >
            {!file ? (
              <div className="flex flex-col items-center justify-center space-y-4">
                <div className="rounded-full bg-primary/10 p-4">
                  <UploadIcon className="h-8 w-8 text-primary" />
                </div>
                <div>
                  <p className="text-lg font-medium">
                    Drag and drop your video here
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Or click to browse files
                  </p>
                </div>
                <input
                  id="file-upload"
                  type="file"
                  accept="video/*"
                  className="hidden"
                  onChange={handleFileChange}
                />
              </div>
            ) : (
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4">
                  <div className="rounded-full bg-primary/10 p-3">
                    <File className="h-6 w-6 text-primary" />
                  </div>
                  <div className="text-left">
                    <p className="font-medium truncate max-w-[200px] sm:max-w-[300px]">
                      {file.name}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {(file.size / (1024 * 1024)).toFixed(2)} MB
                    </p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={(e) => {
                    e.stopPropagation();
                    removeFile();
                  }}
                  disabled={uploading}
                >
                  <X className="h-5 w-5" />
                  <span className="sr-only">Remove file</span>
                </Button>
              </div>
            )}
          </div>

          {file && (
            <div className="space-y-4">
              {uploading && (
                <div className="space-y-2">
                  <p className="text-sm text-center text-muted-foreground">
                    {uploadStatus}
                  </p>
                </div>
              )}
              {error && (
                <p className="text-sm text-center text-red-500">{error}</p>
              )}
              <Button
                className="w-full"
                onClick={() => handleUpload(file)}
                disabled={uploading}
              >
                {uploading ? "Processing..." : "Upload and Process"}
              </Button>
            </div>
          )}
        </TabsContent>

        <TabsContent value="url">
          <div className="space-y-4">
            <div className="flex flex-col items-center justify-center space-y-4 p-12 border-2 border-dashed rounded-lg border-muted-foreground/25">
              <div className="rounded-full bg-primary/10 p-4">
                <Link className="h-8 w-8 text-primary" />
              </div>
              <div className="w-full max-w-md space-y-4">
                <Input
                  type="text"
                  placeholder="Enter YouTube URL"
                  value={youtubeUrl}
                  onChange={(e) => setYoutubeUrl(e.target.value)}
                  className="w-full"
                  disabled={uploading}
                />
                {error && (
                  <p className="text-sm text-center text-red-500">{error}</p>
                )}
                {uploading && (
                  <div className="space-y-2">
                    <p className="text-sm text-center text-muted-foreground">
                      {uploadStatus}
                    </p>
                    <Progress value={undefined} className="w-full" />
                  </div>
                )}
                <Button
                  className="w-full"
                  onClick={handleYoutubeUrlSubmit}
                  disabled={uploading}
                >
                  {uploading ? (
                    <div className="flex items-center space-x-2">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Processing...</span>
                    </div>
                  ) : (
                    "Process YouTube Video"
                  )}
                </Button>
              </div>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
