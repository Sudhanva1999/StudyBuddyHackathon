// import { useState } from "react";
import { Suspense } from "react";
import { Upload } from "@/components/upload";

export default function Home() {
  return (
    <div className="min-h-screen bg-background">
      <main className="container py-10">
        <div className="mx-auto max-w-3xl space-y-8">
          <div className="space-y-2 text-center">
            <h2 className="text-3xl font-bold tracking-tight">
              Upload Your Video
            </h2>
            <p className="text-muted-foreground">
              We&apos;ll convert it to audio, generate a transcript, and create
              a summary you can chat with.
            </p>
          </div>
          <Suspense
            fallback={
              <div className="h-64 flex items-center justify-center">
                Loading...
              </div>
            }
          >
            <Upload />
          </Suspense>
        </div>
      </main>
    </div>
  );
}
