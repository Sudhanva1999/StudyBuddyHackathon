"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2 } from "lucide-react";
import { Progress } from "@/components/ui/progress";

export default function ProcessingPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const filename = searchParams.get("filename") || "video";
  const taskId = localStorage.getItem("taskId");

  const [status, setStatus] = useState("uploaded");
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<any>(null);

  const steps = [
    { id: "uploaded", name: "File uploaded" },
    { id: "converting", name: "Converting video to audio" },
    { id: "transcribing", name: "Generating transcript" },
    { id: "summarizing", name: "Creating summary" },
    { id: "generating_notes", name: "Generating notes" },
    { id: "completed", name: "Processing complete" },
  ];

  const getCurrentStep = () => {
    return steps.findIndex((step) => step.id === status);
  };

  useEffect(() => {
    if (!taskId) {
      console.error("No taskId found in localStorage");
      router.push("/");
      return;
    }

    console.log("Starting status polling for taskId:", taskId);

    const pollStatus = async () => {
      try {
        console.log("Polling status for taskId:", taskId);
        const response = await fetch(`http://localhost:5001/status/${taskId}`);
        
        if (!response.ok) {
          const errorText = await response.text();
          console.error("Status fetch failed:", response.status, errorText);
          throw new Error(`Failed to fetch status: ${response.status} ${errorText}`);
        }

        const data = await response.json();
        console.log("Received status data:", data);
        
        setStatus(data.status);

        if (data.status === "completed") {
          console.log("Processing completed, results:", data.results);
          if (!data.results) {
            console.error("No results found in completed response");
            setError("Processing completed but no results were returned");
            return;
          }
          setResults(data.results);
          // Store results in localStorage for the results page
          try {
            localStorage.setItem("processingResults", JSON.stringify(data.results));
            console.log("Results stored in localStorage");
            
            // Verify the data was stored correctly
            const storedData = localStorage.getItem("processingResults");
            if (!storedData) {
              throw new Error("Failed to store results in localStorage");
            }
            
            // Navigate to results page after a short delay
            setTimeout(() => {
              router.push(`/results?filename=${encodeURIComponent(filename)}`);
            }, 1500);
          } catch (error) {
            console.error("Error storing results:", error);
            setError("Failed to store processing results");
          }
        } else if (data.status === "error") {
          console.error("Processing error:", data.error);
          setError(data.error || "An error occurred during processing");
        }
      } catch (err) {
        console.error("Error during status polling:", err);
        setError(err instanceof Error ? err.message : "Failed to fetch status");
      }
    };

    // Poll every 2 seconds
    const interval = setInterval(pollStatus, 2000);

    // Initial poll
    pollStatus();

    return () => {
      console.log("Cleaning up polling interval");
      clearInterval(interval);
    };
  }, [taskId, filename, router]);

  if (error) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="max-w-md w-full p-6 space-y-8">
          <div className="text-center space-y-2">
            <h1 className="text-2xl font-bold text-destructive">Error</h1>
            <p className="text-muted-foreground">{error}</p>
            <button
              onClick={() => router.push("/")}
              className="mt-4 px-4 py-2 bg-primary text-primary-foreground rounded-md"
            >
              Return to Upload
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <div className="max-w-md w-full p-6 space-y-8">
        <div className="text-center space-y-2">
          <h1 className="text-2xl font-bold">Processing Your Video</h1>
          <p className="text-muted-foreground">
            Please wait while we process &quot;{filename}&quot;
          </p>
        </div>

        <div className="space-y-8 mt-8">
          {steps.map((step, index) => {
            const currentStepIndex = getCurrentStep();
            const isCompleted = currentStepIndex > index;
            const isCurrent = currentStepIndex === index;

            return (
              <div key={step.id} className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div
                      className={`rounded-full p-2 ${
                        isCompleted
                          ? "bg-primary/20 text-primary"
                          : isCurrent
                          ? "bg-primary text-primary-foreground"
                          : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {isCompleted ? (
                        <svg
                          className="h-4 w-4"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M5 13l4 4L19 7"
                          />
                        </svg>
                      ) : isCurrent ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <span className="h-4 w-4 flex items-center justify-center text-xs">
                          {index + 1}
                        </span>
                      )}
                    </div>
                    <span
                      className={
                        currentStepIndex >= index
                          ? "font-medium"
                          : "text-muted-foreground"
                      }
                    >
                      {step.name}
                    </span>
                  </div>
                  {isCompleted && (
                    <span className="text-sm text-primary">Completed</span>
                  )}
                </div>

                {isCurrent && (
                  <div className="space-y-1">
                    <Progress value={100} className="h-2" />
                    <p className="text-xs text-right text-muted-foreground">
                      Processing...
                    </p>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
