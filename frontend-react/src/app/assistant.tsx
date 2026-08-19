"use client";

import { AiSdkRuntimeProvider } from "@/components/assistant-ui/aisdk-runtime-provider";
import { Thread } from "@/components/assistant-ui/thread";

export default function Assistant() {
  return (
    <AiSdkRuntimeProvider>
      <Thread />
    </AiSdkRuntimeProvider>
  );
}