"use client";

import type React from "react";

import { useState, useRef, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { downloadPdfFromHtml } from "../../helpers/markdown-to-pdf";
import {
  Download,
  MessageSquare,
  FileText,
  Play,
  Pause,
  Volume2,
  VolumeX,
  GripVertical,
  BookOpen,
  GitBranch,
} from "lucide-react";
import { ChatInterface } from "@/components/chat-interface";
import {
  ResizablePanel,
  ResizablePanelGroup,
  ResizableHandle,
} from "@/components/ui/resizable";
import { FlashCards } from "@/components/flash-cards";
import { MindMap } from "@/components/mind-map";

// Mock data for demonstration
const mockTranscript = `
Speaker 1: Welcome to our discussion on artificial intelligence and its impact on society.
Speaker 2: Thank you for having me. It's an important topic that deserves attention.
Speaker 1: Let's start with the basics. How would you define AI for our audience?
Speaker 2: Artificial Intelligence refers to computer systems designed to perform tasks that typically require human intelligence. These include learning, reasoning, problem-solving, perception, and language understanding.
Speaker 1: And how is AI currently being used in everyday applications?
Speaker 2: AI is all around us. From voice assistants like Siri and Alexa to recommendation systems on streaming platforms and e-commerce sites. It's in our email spam filters, navigation apps, and increasingly in healthcare for diagnostics.
`;

const mockSummary = `
This discussion explores artificial intelligence and its societal impact. The speakers define AI as computer systems designed to perform tasks requiring human intelligence, including learning, reasoning, and language understanding. They highlight AI's prevalence in everyday applications such as voice assistants, recommendation systems, email filters, navigation apps, and healthcare diagnostics. The conversation emphasizes AI's growing importance and integration into daily life.
`;

export default function ResultsPage() {
  const searchParams = useSearchParams();
  const [data, setData] = useState<any>(null);
  const filename = searchParams.get("filename") || "video";
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("transcript");
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const videoRef = useRef<HTMLVideoElement>(null);
  const taskId = localStorage.getItem("taskId");
  const [flashcardsKey, setFlashcardsKey] = useState(0);

  console.log("ResultsPage rendered with taskId:", taskId);

  // load transcript and summary data from localStorage
  useEffect(() => {
    const fetchData = () => {
      console.log("Fetching results data from localStorage");
      const storedData = localStorage.getItem("processingResults");
      if (storedData) {
        try {
          const parsedData = JSON.parse(storedData);
          console.log("Loaded results data:", parsedData);
          console.log("Results data keys:", Object.keys(parsedData));
          if (parsedData.flashcards) {
            console.log("Flashcards in results data:", parsedData.flashcards.length);
          } else {
            console.warn("No flashcards in results data");
          }
          setData(parsedData);
        } catch (error) {
          console.error("Error parsing stored data:", error);
          setData(null);
        }
      } else {
        console.warn("No results data found in localStorage");
        setData(null);
      }
    };

    fetchData();
  }, []);

  // Load video from sessionStorage
  useEffect(() => {
    const videoUrl = sessionStorage.getItem("videoUrl");
    if (videoUrl) {
      console.log("Video URL found in sessionStorage");
      setVideoUrl(videoUrl);
    } else {
      console.warn("No video URL found in sessionStorage");
      setVideoUrl(null);
    }

    // Clean up the video URL when component unmounts
    return () => {
      if (videoUrl) {
        URL.revokeObjectURL(videoUrl);
      }
    };
  }, []);

  const handlePlayPause = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  const handleMute = () => {
    if (videoRef.current) {
      videoRef.current.muted = !isMuted;
      setIsMuted(!isMuted);
    }
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
    }
  };

  const formatTime = (time: number) => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds < 10 ? "0" : ""}${seconds}`;
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newTime = Number.parseFloat(e.target.value);
    setCurrentTime(newTime);
    if (videoRef.current) {
      videoRef.current.currentTime = newTime;
    }
  };

  const downloadPDF = () => {
    downloadPdfFromHtml(
      document.getElementById("lecture-notes-div")?.innerHTML
    );
  };

  const handleTabChange = (value: string) => {
    console.log("Tab changed to:", value);
    setActiveTab(value);
    // Force re-render of flashcards component when tab is activated
    if (value === "flashcards") {
      console.log("Flashcards tab activated, incrementing key");
      setFlashcardsKey(prev => prev + 1);
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b">
        <div className="container flex h-16 items-center justify-between">
          <h1 className="text-2xl font-bold">StudyBuddy</h1>
          <Button
            variant="outline"
            onClick={() => (window.location.href = "/")}
          >
            New Upload
          </Button>
        </div>
      </header>

      <main className="m-4 py-8">
        <h2 className="text-3xl font-bold mb-6">{filename}</h2>

        <ResizablePanelGroup
          direction="horizontal"
          className="min-h-[600px] rounded-lg border"
        >
          {/* Video Panel */}
          <ResizablePanel defaultSize={60} minSize={30}>
            <div className="h-full p-4 space-y-4">
              <div className="relative bg-black aspect-video rounded-md overflow-hidden">
                {videoUrl ? (
                  <video
                    ref={videoRef}
                    className="w-full h-full"
                    src={videoUrl}
                    controls={false}
                    onTimeUpdate={handleTimeUpdate}
                    onLoadedMetadata={handleLoadedMetadata}
                    onError={(e) => {
                      console.error("Error loading video:", e);
                      setVideoUrl(null);
                    }}
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-muted-foreground">
                    Video not available
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">
                    {formatTime(currentTime)} / {formatTime(duration)}
                  </span>
                  <div className="flex items-center space-x-2">
                    <Button variant="ghost" size="icon" onClick={handleMute}>
                      {isMuted ? (
                        <VolumeX className="h-5 w-5" />
                      ) : (
                        <Volume2 className="h-5 w-5" />
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={handlePlayPause}
                    >
                      {isPlaying ? (
                        <Pause className="h-5 w-5" />
                      ) : (
                        <Play className="h-5 w-5" />
                      )}
                    </Button>
                  </div>
                </div>

                <input
                  type="range"
                  min="0"
                  max={duration || 100}
                  value={currentTime}
                  onChange={handleSeek}
                  className="w-full h-2 bg-muted rounded-full appearance-none cursor-pointer"
                />
              </div>
            </div>
          </ResizablePanel>

          <ResizableHandle withHandle>
            <div className="h-full flex items-center justify-center">
              <GripVertical className="h-4 w-4 text-muted-foreground" />
            </div>
          </ResizableHandle>

          {/* Content Panel */}
          <ResizablePanel defaultSize={40} minSize={35}>
            <div className="h-full p-4">
              <Tabs
                value={activeTab}
                onValueChange={handleTabChange}
                className="w-full"
              >
                <TabsList className="grid w-full grid-cols-5">
                  <TabsTrigger
                    value="transcript"
                    className="flex items-center gap-2"
                  >
                    <FileText className="h-4 w-4" />
                    <span>Transcript</span>
                  </TabsTrigger>
                  <TabsTrigger
                    value="summary"
                    className="flex items-center gap-2"
                  >
                    <FileText className="h-4 w-4" />
                    <span>Notes</span>
                  </TabsTrigger>
                  <TabsTrigger value="chat" className="flex items-center gap-2">
                    <MessageSquare className="h-4 w-4" />
                    <span>Chat</span>
                  </TabsTrigger>
                  <TabsTrigger value="flashcards" className="flex items-center gap-2">
                    <BookOpen className="h-4 w-4" />
                    <span>Flashcards</span>
                  </TabsTrigger>
                  <TabsTrigger value="mindmap" className="flex items-center gap-2">
                    <GitBranch className="h-4 w-4" />
                    <span>Mind Map</span>
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="transcript" className="mt-4">
                  <Card className="p-6 h-[500px] overflow-y-auto">
                    <div className="prose dark:prose-invert max-w-none">
                      <h3 className="text-xl font-semibold mb-4">Transcript</h3>
                      <div className="whitespace-pre-line">
                        {data?.transcript?.text || "Loading..."}
                      </div>
                    </div>
                  </Card>
                </TabsContent>

                <TabsContent value="summary" className="mt-4">
                  <Card className="p-6 h-[500px] overflow-y-auto">
                    <div className="prose dark:prose-invert max-w-none">
                      <div className="flex items-center justify-between mb-4">
                        <h3 className="text-xl font-semibold">
                          Summary & Notes
                        </h3>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={downloadPDF}
                          className="flex items-center gap-2"
                        >
                          <Download className="h-4 w-4" />
                          <span>Download PDF</span>
                        </Button>
                      </div>
                      <div id="lecture-notes-div" className="prose markdown">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {data?.notes || "Loading..."}
                        </ReactMarkdown>
                      </div>
                    </div>
                  </Card>
                </TabsContent>

                <TabsContent value="chat" className="mt-4">
                  <Card className="p-0 overflow-hidden h-[500px]">
                    <ChatInterface summary={data?.summary || ""} />
                  </Card>
                </TabsContent>

                <TabsContent value="flashcards" className="mt-4">
                  <Card className="p-0 overflow-hidden h-[500px]">
                    {taskId ? (
                      <>
                        <div className="p-2 text-xs text-muted-foreground">
                          Task ID: {taskId} | Key: {flashcardsKey}
                        </div>
                        <FlashCards key={flashcardsKey} taskId={taskId} />
                      </>
                    ) : (
                      <div className="flex items-center justify-center h-full text-gray-500">
                        No flashcards available
                      </div>
                    )}
                  </Card>
                </TabsContent>

                <TabsContent value="mindmap" className="mt-4">
                  <Card className="p-0 overflow-hidden h-[500px]">
                    {taskId ? (
                      <>
                        <div className="p-2 text-xs text-muted-foreground">
                          Task ID: {taskId}
                        </div>
                        <MindMap taskId={taskId} />
                      </>
                    ) : (
                      <div className="flex items-center justify-center h-full text-gray-500">
                        No mind map available
                      </div>
                    )}
                  </Card>
                </TabsContent>
              </Tabs>
            </div>
          </ResizablePanel>
        </ResizablePanelGroup>
      </main>
    </div>
  );
}
