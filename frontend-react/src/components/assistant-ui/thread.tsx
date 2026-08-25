"use client";

import {
  ComposerAddAttachment,
  ComposerAttachments,
  UserMessageAttachments,
} from "@/components/assistant-ui/attachment";
import { ThreadFollowupSuggestions } from "@/components/assistant-ui/follow-up-suggestions";
import { MarkdownText } from "@/components/assistant-ui/markdown-text";
import {
  Reasoning,
  ReasoningContent,
  ReasoningRoot,
  ReasoningText,
  ReasoningTrigger,
} from "@/components/assistant-ui/reasoning";
import { ToolFallback } from "@/components/assistant-ui/tool-fallback";
import { KbRetrievalRenderer } from "@/components/assistant-ui/tool-renderers/kb-retrieval";
import { ConfirmActionRenderer } from "@/components/assistant-ui/tool-renderers/confirm-action";
import { WorkflowControlRenderer } from "@/components/assistant-ui/tool-renderers/workflow-control";
import { WorkflowDataRenderer } from "@/components/assistant-ui/workflow-card";
import { ResearchDataRenderer } from "@/components/assistant-ui/research-card";
import { selectHasActiveWorkflow, useWorkflowUiStore } from "@/lib/stores/workflow";
import { type ResearchMode, useResearchModeStore } from "@/lib/stores/research";
import {
  ToolGroupContent,
  ToolGroupRoot,
  ToolGroupTrigger,
} from "@/components/assistant-ui/tool-group";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { A2UIRenderer } from "@/components/a2ui/A2UIRenderer";
import { BrandMark } from "@/components/brand/brand-mark";
import {
  ActionBarMorePrimitive,
  ActionBarPrimitive,
  AuiIf,
  type AssistantState,
  type DataMessagePartProps,
  BranchPickerPrimitive,
  ComposerPrimitive,
  ErrorPrimitive,
  groupPartByType,
  type GroupByContext,
  MessagePrimitive,
  SuggestionPrimitive,
  ThreadPrimitive,
  type ToolCallMessagePartComponent,
  useAuiState,
  useAssistantDataUI,
} from "@assistant-ui/react";
import {
  ArrowClockwise as RefreshCwIcon,
  ArrowDown as ArrowDownIcon,
  ArrowUp as ArrowUpIcon,
  CaretLeft as ChevronLeftIcon,
  CaretRight as ChevronRightIcon,
  Check as CheckIcon,
  Copy as CopyIcon,
  DotsThree as MoreHorizontalIcon,
  DownloadSimple as DownloadIcon,
  Microphone as MicIcon,
  MagnifyingGlass as SearchIcon,
  PencilSimple as PencilIcon,
  Square as SquareIcon,
} from "@phosphor-icons/react";
import {
  createContext,
  useContext,
  type ComponentType,
  type FC,
  type PropsWithChildren,
} from "react";

export type ThreadGroupPart = MessagePrimitive.GroupedParts.GroupPart;

/**
 * Optional component overrides for the thread. `AssistantMessage` and
 * `Welcome` replace whole sections; the remaining slots override how the
 * assistant message renders tool calls and part groups. Tool UIs registered
 * by name (toolkit `render`, `useAssistantDataUI`) take precedence over
 * `ToolFallback`.
 */
export type ThreadComponents = {
  AssistantMessage?: ComponentType | undefined;
  Welcome?: ComponentType | undefined;
  ToolFallback?: ToolCallMessagePartComponent | undefined;
  ToolGroup?:
    | ComponentType<PropsWithChildren<{ group: ThreadGroupPart }>>
    | undefined;
  ReasoningGroup?:
    | ComponentType<PropsWithChildren<{ group: ThreadGroupPart }>>
    | undefined;
};

export type ThreadProps = {
  components?: ThreadComponents | undefined;
};

const EMPTY_COMPONENTS: ThreadComponents = {};

const ThreadComponentsContext =
  createContext<ThreadComponents>(EMPTY_COMPONENTS);

const A2UIDataRenderer: FC<DataMessagePartProps<any>> = ({ data }) => {
  const schema = data && typeof data === "object" && "schema" in data
    ? data.schema
    : data;
  return <A2UIRenderer schema={schema} />;
};

// Startup exposes a loading placeholder thread; treat it as a new chat so
// the composer mounts centered. Loads after startup keep the docked layout.
const isNewChatView = (s: AssistantState) =>
  s.thread.messages.length === 0 &&
  (!s.thread.isLoading || s.threads.isLoading);

export const Thread: FC<ThreadProps> = ({ components = EMPTY_COMPONENTS }) => {
  useAssistantDataUI({ name: "a2ui", render: A2UIDataRenderer });
  useAssistantDataUI({ name: "workflow", render: WorkflowDataRenderer });
  useAssistantDataUI({ name: "research", render: ResearchDataRenderer });
  const isEmpty = useAuiState(isNewChatView);

  return (
    <ThreadComponentsContext.Provider value={components}>
      <ThreadRoot isEmpty={isEmpty} />
    </ThreadComponentsContext.Provider>
  );
};

const ThreadRoot: FC<{ isEmpty: boolean }> = ({ isEmpty }) => {
  const { Welcome = ThreadWelcome } = useContext(ThreadComponentsContext);

  return (
    <ThreadPrimitive.Root
      className="aui-root aui-thread-root bg-background @container flex h-full flex-col"
      style={{
        ["--thread-max-width" as string]: "49rem",
        ["--composer-bg" as string]:
          "color-mix(in oklab, hsl(var(--surface-elevated)) 92%, hsl(var(--background)))",
        ["--composer-radius" as string]: "18px",
        ["--composer-padding" as string]: "10px",
      }}
    >
      <ThreadPrimitive.Viewport
        turnAnchor="top"
        data-slot="aui_thread-viewport"
        className="relative flex flex-1 flex-col overflow-x-auto overflow-y-scroll scroll-smooth [scrollbar-gutter:stable]"
      >
        <div
          className={cn(
            "mx-auto flex w-full max-w-[var(--thread-max-width)] flex-1 flex-col px-4 pt-14 sm:px-7",
            isEmpty && "justify-center",
          )}
        >
          <AuiIf condition={isNewChatView}>
            <Welcome />
          </AuiIf>

          <div
            data-slot="aui_message-group"
            className="mb-14 flex flex-col gap-y-6 empty:hidden"
          >
            <ThreadPrimitive.Messages>
              {() => <ThreadMessage />}
            </ThreadPrimitive.Messages>
          </div>

          <ThreadPrimitive.ViewportFooter
            className={cn(
              "aui-thread-viewport-footer flex flex-col gap-3 overflow-visible pb-[max(1rem,env(safe-area-inset-bottom))] md:pb-6",
              !isEmpty &&
                "sticky bottom-0 mt-auto rounded-t-[var(--composer-radius)] bg-gradient-to-t from-background via-background to-background/0 pt-8",
            )}
          >
            <ThreadScrollToBottom />
            <ThreadFollowupSuggestions />
            <Composer />
            <AuiIf condition={(s) => isNewChatView(s) && s.composer.isEmpty}>
              <ThreadSuggestions />
            </AuiIf>
          </ThreadPrimitive.ViewportFooter>
        </div>
      </ThreadPrimitive.Viewport>
    </ThreadPrimitive.Root>
  );
};

const ThreadMessage: FC = () => {
  const { AssistantMessage: AssistantMessageComponent = AssistantMessage } =
    useContext(ThreadComponentsContext);
  const role = useAuiState((s) => s.message.role);
  const isEditing = useAuiState((s) => s.message.composer.isEditing);

  if (isEditing) return <EditComposer />;
  if (role === "user") return <UserMessage />;
  return <AssistantMessageComponent />;
};

const ThreadScrollToBottom: FC = () => {
  return (
    <ThreadPrimitive.ScrollToBottom asChild>
      <TooltipIconButton
        tooltip="回到最新消息"
        variant="outline"
        className="aui-thread-scroll-to-bottom absolute -top-10 z-10 size-9 self-center rounded-full border-border/70 bg-background/90 p-2 shadow-panel backdrop-blur disabled:invisible"
      >
        <ArrowDownIcon />
      </TooltipIconButton>
    </ThreadPrimitive.ScrollToBottom>
  );
};

const ThreadWelcome: FC = () => {
  return (
    <div className="aui-thread-welcome-root mb-8 flex flex-col items-center px-4 text-center">
      <div className="mb-7 flex size-16 items-center justify-center rounded-[20px] border border-primary/20 bg-primary/8 shadow-[0_18px_60px_-28px_hsl(var(--primary)/0.65)]">
        <BrandMark className="scale-125 text-primary" />
      </div>
      <p className="text-[11px] font-medium tracking-[0.16em] text-primary">观心助理</p>
      <h1 className="aui-thread-welcome-message-inner fade-in slide-in-from-bottom-1 animate-in mt-3 fill-mode-both text-2xl font-semibold tracking-[-0.035em] duration-200 sm:text-[30px]">
        从问题出发，看见完整执行过程
      </h1>
      <p className="mt-3 max-w-lg text-sm leading-6 text-muted-foreground">
        检索知识、调用工具、分析数据。每一步都有依据，也可以随时介入。
      </p>
    </div>
  );
};

const ThreadSuggestions: FC = () => {
  return (
    <div className="aui-thread-welcome-suggestions flex w-full flex-wrap items-center justify-center gap-2 px-4">
      <ThreadPrimitive.Suggestions>
        {() => <ThreadSuggestionItem />}
      </ThreadPrimitive.Suggestions>
    </div>
  );
};

const ThreadSuggestionItem: FC = () => {
  return (
    <div className="aui-thread-welcome-suggestion-display fade-in slide-in-from-bottom-2 animate-in fill-mode-both duration-200">
      <SuggestionPrimitive.Trigger send asChild>
        <Button
          variant="ghost"
          className="aui-thread-welcome-suggestion h-auto gap-1.5 rounded-[12px] border border-border/70 bg-background/70 px-3.5 py-2 text-sm font-normal whitespace-nowrap text-foreground shadow-panel transition-colors hover:border-primary/25 hover:bg-primary/5"
        >
          <SuggestionPrimitive.Title className="aui-thread-welcome-suggestion-text-1" />
          <SuggestionPrimitive.Description className="aui-thread-welcome-suggestion-text-2 empty:hidden" />
        </Button>
      </SuggestionPrimitive.Trigger>
    </div>
  );
};

const Composer: FC = () => {
  const hasActiveWorkflow = useWorkflowUiStore(selectHasActiveWorkflow);
  return (
    <ComposerPrimitive.Root className="aui-composer-root relative flex w-full flex-col">
      <ComposerPrimitive.AttachmentDropzone asChild>
        <div
          data-slot="aui_composer-shell"
          data-locked={hasActiveWorkflow ? "true" : "false"}
          className="flex w-full flex-col gap-2.5 rounded-[var(--composer-radius)] border border-border/75 bg-[var(--composer-bg)] p-[var(--composer-padding)] shadow-float transition-[border-color,box-shadow,background-color] duration-200 focus-within:border-primary/35 focus-within:ring-4 focus-within:ring-primary/10 data-[dragging=true]:border-dashed data-[dragging=true]:border-primary/50 data-[dragging=true]:bg-accent/70 data-[dragging=true]:ring-4 data-[dragging=true]:ring-primary/10 data-[locked=true]:border-border/55 data-[locked=true]:bg-muted/60 data-[locked=true]:shadow-none dark:border-border/80 dark:focus-within:border-primary/40"
        >
          <ComposerAttachments />
          <ComposerPrimitive.Input
            placeholder={hasActiveWorkflow ? "请先处理或取消当前工作流" : "描述任务，或直接问一个问题"}
            className="aui-composer-input max-h-44 min-h-14 w-full resize-none bg-transparent px-3 py-2 text-base leading-6 text-foreground caret-primary outline-none placeholder:text-muted-foreground/70 disabled:cursor-not-allowed disabled:text-muted-foreground sm:min-h-16 sm:text-[15px]"
            rows={1}
            autoFocus
            enterKeyHint="send"
            aria-label="输入消息"
            disabled={hasActiveWorkflow}
          />
          <ComposerAction disabled={hasActiveWorkflow} />
        </div>
      </ComposerPrimitive.AttachmentDropzone>
    </ComposerPrimitive.Root>
  );
};

const ComposerAction: FC<{ disabled?: boolean }> = ({ disabled = false }) => {
  return (
    <div className="aui-composer-action-wrapper relative flex min-h-9 items-center justify-between gap-2 px-0.5">
      <div className="flex min-w-0 items-center gap-1.5">
        <ComposerAddAttachment disabled={disabled} />
        <ResearchModeSelect disabled={disabled} />
      </div>
      <div className="flex shrink-0 items-center gap-1.5">
        <AuiIf condition={(s) => s.thread.capabilities.dictation}>
          <AuiIf condition={(s) => s.composer.dictation == null}>
            <ComposerPrimitive.Dictate asChild>
              <TooltipIconButton
                tooltip="语音输入"
                side="bottom"
                type="button"
                variant="ghost"
                size="icon"
                className="aui-composer-dictate size-8 rounded-full text-muted-foreground hover:text-foreground"
                aria-label="开始语音输入"
                {...(disabled ? { disabled: true } : {})}
              >
                <MicIcon className="aui-composer-dictate-icon size-4" />
              </TooltipIconButton>
            </ComposerPrimitive.Dictate>
          </AuiIf>
          <AuiIf condition={(s) => s.composer.dictation != null}>
            <ComposerPrimitive.StopDictation asChild>
              <TooltipIconButton
                tooltip="停止语音输入"
                side="bottom"
                type="button"
                variant="ghost"
                size="icon"
                className="aui-composer-stop-dictation size-8 rounded-full text-destructive"
                aria-label="停止语音输入"
                {...(disabled ? { disabled: true } : {})}
              >
                <SquareIcon className="aui-composer-stop-dictation-icon size-3.5 animate-pulse fill-current" />
              </TooltipIconButton>
            </ComposerPrimitive.StopDictation>
          </AuiIf>
        </AuiIf>
        <AuiIf condition={(s) => !s.thread.isRunning}>
          <ComposerPrimitive.Send asChild>
            <TooltipIconButton
              tooltip="发送消息"
              side="bottom"
              type="button"
              variant="default"
              size="icon"
              className="aui-composer-send size-9 rounded-full shadow-[0_8px_20px_-12px_hsl(var(--primary)/0.9)] disabled:shadow-none"
              aria-label="发送消息"
              {...(disabled ? { disabled: true } : {})}
            >
              <ArrowUpIcon className="aui-composer-send-icon size-4.5" />
            </TooltipIconButton>
          </ComposerPrimitive.Send>
        </AuiIf>
        <AuiIf condition={(s) => s.thread.isRunning}>
          <ComposerPrimitive.Cancel asChild>
            <Button
              type="button"
              variant="default"
              size="icon"
              className="aui-composer-cancel size-9 rounded-full shadow-[0_8px_20px_-12px_hsl(var(--primary)/0.9)]"
              aria-label="停止生成"
            >
              <SquareIcon className="aui-composer-cancel-icon size-3.5 fill-current" />
            </Button>
          </ComposerPrimitive.Cancel>
        </AuiIf>
      </div>
    </div>
  );
};

const ResearchModeSelect: FC<{ disabled?: boolean }> = ({ disabled = false }) => {
  const mode = useResearchModeStore((state) => state.mode);
  const setMode = useResearchModeStore((state) => state.setMode);
  return (
    <Select value={mode} onValueChange={(value) => setMode(value as ResearchMode)} disabled={disabled}>
      <SelectTrigger
        className="h-8 w-auto min-w-[112px] gap-1.5 rounded-full border border-border/55 bg-muted/55 px-2.5 text-xs text-muted-foreground shadow-none transition-colors hover:border-border hover:bg-muted hover:text-foreground focus:ring-1 focus:ring-primary/25 focus:ring-offset-0"
        aria-label="研究模式"
      >
        <SearchIcon size={13} />
        <SelectValue />
      </SelectTrigger>
      <SelectContent align="start">
        <SelectItem value="auto">自动</SelectItem>
        <SelectItem value="quick">快速研究</SelectItem>
        <SelectItem value="deep">深度研究</SelectItem>
      </SelectContent>
    </Select>
  );
};

const MessageError: FC = () => {
  return (
    <MessagePrimitive.Error>
      <ErrorPrimitive.Root className="aui-message-error-root border-destructive bg-destructive/10 text-destructive dark:bg-destructive/5 mt-2 rounded-md border p-3 text-sm dark:text-red-200">
        <ErrorPrimitive.Message className="aui-message-error-message line-clamp-2" />
      </ErrorPrimitive.Root>
    </MessagePrimitive.Error>
  );
};

const defaultAssistantGroupBy = groupPartByType({
  reasoning: ["group-chainOfThought", "group-reasoning"],
  "tool-call": ["group-chainOfThought", "group-tool"],
  "standalone-tool-call": [],
});

const assistantGroupBy: typeof defaultAssistantGroupBy = (
  part,
  context?: GroupByContext,
) => {
  if (part.type === "tool-call" && part.toolName === "workflow_control") {
    return [];
  }
  return defaultAssistantGroupBy(part, context);
};

const AssistantMessage: FC = () => {
  const {
    ToolFallback: ToolFallbackComponent = ToolFallback,
    ToolGroup,
    ReasoningGroup,
  } = useContext(ThreadComponentsContext);

  const ACTION_BAR_PT = "pt-1.5";
  // Keep the action bar inside the contained root's paint box, then cancel its reserved space in flow.
  const ACTION_BAR_HEIGHT = `min-h-7.5 ${ACTION_BAR_PT}`;

  return (
    <MessagePrimitive.Root
      data-slot="aui_assistant-message-root"
      data-role="assistant"
      className="fade-in slide-in-from-bottom-1 animate-in relative -mb-7.5 pb-7.5 duration-150 [contain-intrinsic-size:auto_200px] [content-visibility:auto]"
    >
      <div
        data-slot="aui_assistant-message-content"
        className="text-foreground px-2 leading-relaxed wrap-break-word"
      >
        <MessagePrimitive.GroupedParts groupBy={assistantGroupBy}>
          {({ part, children }) => {
            switch (part.type) {
              case "group-chainOfThought":
                return <div data-slot="aui_chain-of-thought">{children}</div>;
              case "group-tool":
                if (ToolGroup) {
                  return <ToolGroup group={part}>{children}</ToolGroup>;
                }
                return (
                  <ToolGroupRoot variant="ghost" defaultOpen>
                    <ToolGroupTrigger
                      count={part.indices.length}
                      active={part.status.type === "running"}
                    />
                    <ToolGroupContent>{children}</ToolGroupContent>
                  </ToolGroupRoot>
                );
              case "group-reasoning": {
                if (ReasoningGroup) {
                  return (
                    <ReasoningGroup group={part}>{children}</ReasoningGroup>
                  );
                }
                const running = part.status.type === "running";
                return (
                  <ReasoningRoot streaming={running}>
                    <ReasoningTrigger active={running} />
                    <ReasoningContent aria-busy={running}>
                      <ReasoningText>{children}</ReasoningText>
                    </ReasoningContent>
                  </ReasoningRoot>
                );
              }
              case "text":
                return <MarkdownText />;
              case "reasoning":
                return <Reasoning {...part} />;
              case "tool-call": {
                // Map agent tool names to custom renderers
                if (part.toolUI) return part.toolUI;
                if (part.toolName === "confirm_action")
                  return <ConfirmActionRenderer {...(part as any)} />;
                if (part.toolName === "workflow_control")
                  return <WorkflowControlRenderer {...(part as any)} />;
                if (part.toolName === "kb_retrieval")
                  return <KbRetrievalRenderer {...(part as any)} />;
                return <ToolFallbackComponent {...part} />;
              }
              case "data":
                return part.dataRendererUI;
              case "indicator":
                return (
                  <span
                    data-slot="aui_assistant-message-indicator"
                    className="animate-pulse font-sans"
                    aria-label="Assistant is working"
                  >
                    {"●"}
                  </span>
                );
              default:
                return null;
            }
          }}
        </MessagePrimitive.GroupedParts>
        <MessageError />
      </div>

      <div
        data-slot="aui_assistant-message-footer"
        className={cn("ms-2 flex items-center", ACTION_BAR_HEIGHT)}
      >
        <BranchPicker />
        <AssistantActionBar />
      </div>
    </MessagePrimitive.Root>
  );
};

const AssistantActionBar: FC = () => {
  return (
    <ActionBarPrimitive.Root
      hideWhenRunning
      autohide="not-last"
      className="aui-assistant-action-bar-root text-muted-foreground animate-in fade-in col-start-3 row-start-2 -ms-1 flex gap-1 duration-200"
    >
      <ActionBarPrimitive.Copy asChild>
        <TooltipIconButton tooltip="复制">
          <AuiIf condition={(s) => s.message.isCopied}>
            <CheckIcon className="animate-in zoom-in-50 fade-in duration-200 ease-out" />
          </AuiIf>
          <AuiIf condition={(s) => !s.message.isCopied}>
            <CopyIcon className="animate-in zoom-in-75 fade-in duration-150" />
          </AuiIf>
        </TooltipIconButton>
      </ActionBarPrimitive.Copy>
      <ActionBarPrimitive.Reload asChild>
        <TooltipIconButton tooltip="重新生成">
          <RefreshCwIcon />
        </TooltipIconButton>
      </ActionBarPrimitive.Reload>
      <ActionBarMorePrimitive.Root>
        <ActionBarMorePrimitive.Trigger asChild>
          <TooltipIconButton
            tooltip="更多"
            className="data-[state=open]:bg-accent"
          >
            <MoreHorizontalIcon />
          </TooltipIconButton>
        </ActionBarMorePrimitive.Trigger>
        <ActionBarMorePrimitive.Content
          side="bottom"
          align="start"
          sideOffset={6}
          className="aui-action-bar-more-content bg-popover/95 text-popover-foreground data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=open]:animate-in data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[state=closed]:animate-out data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 z-50 min-w-[8rem] overflow-hidden rounded-xl border p-1.5 shadow-lg backdrop-blur-sm"
        >
          <ActionBarPrimitive.ExportMarkdown asChild>
            <ActionBarMorePrimitive.Item className="aui-action-bar-more-item hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-1.5 text-sm outline-none select-none">
              <DownloadIcon className="size-4" />
              导出为 Markdown
            </ActionBarMorePrimitive.Item>
          </ActionBarPrimitive.ExportMarkdown>
        </ActionBarMorePrimitive.Content>
      </ActionBarMorePrimitive.Root>
    </ActionBarPrimitive.Root>
  );
};

const UserMessage: FC = () => {
  return (
    <MessagePrimitive.Root
      data-slot="aui_user-message-root"
      className="fade-in slide-in-from-bottom-1 animate-in grid auto-rows-auto grid-cols-[minmax(72px,1fr)_auto] content-start gap-y-2 px-2 duration-150 [contain-intrinsic-size:auto_200px] [content-visibility:auto] [&:where(>*)]:col-start-2"
      data-role="user"
    >
      <UserMessageAttachments />

      <div className="aui-user-message-content-wrapper relative col-start-2 min-w-0">
        <div className="aui-user-message-content peer rounded-[14px] border border-border/60 bg-muted/65 px-4 py-2.5 text-foreground shadow-panel wrap-break-word empty:hidden">
          <MessagePrimitive.Parts />
        </div>
        <div className="aui-user-action-bar-wrapper absolute start-0 top-1/2 -translate-x-full -translate-y-1/2 pe-2 peer-empty:hidden rtl:translate-x-full">
          <UserActionBar />
        </div>
      </div>

      <BranchPicker
        data-slot="aui_user-branch-picker"
        className="col-span-full col-start-1 row-start-3 -me-1 justify-end"
      />
    </MessagePrimitive.Root>
  );
};

const UserActionBar: FC = () => {
  return (
    <ActionBarPrimitive.Root
      hideWhenRunning
      autohide="not-last"
      className="aui-user-action-bar-root flex flex-col items-end"
    >
      <ActionBarPrimitive.Edit asChild>
        <TooltipIconButton tooltip="编辑" className="aui-user-action-edit">
          <PencilIcon />
        </TooltipIconButton>
      </ActionBarPrimitive.Edit>
    </ActionBarPrimitive.Root>
  );
};

const EditComposer: FC = () => {
  return (
    <MessagePrimitive.Root
      data-slot="aui_edit-composer-wrapper"
      className="flex flex-col px-2 [contain-intrinsic-size:auto_200px] [content-visibility:auto]"
    >
      <ComposerPrimitive.Root className="aui-edit-composer-root ms-auto flex w-full max-w-full flex-col rounded-[var(--composer-radius)] border border-border/75 bg-[var(--composer-bg)] shadow-panel transition-[border-color,box-shadow] duration-200 focus-within:border-primary/35 focus-within:ring-4 focus-within:ring-primary/10 dark:border-border/80 sm:max-w-[85%]">
        <ComposerPrimitive.Input
          className="aui-edit-composer-input max-h-44 min-h-14 w-full resize-none bg-transparent px-4 pt-3 pb-1 text-base leading-6 text-foreground outline-none placeholder:text-muted-foreground/70 sm:text-[15px]"
          autoFocus
        />
        <div className="aui-edit-composer-footer mx-2.5 mb-2.5 flex items-center gap-1.5 self-end">
          <ComposerPrimitive.Cancel asChild>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 rounded-full px-3.5"
            >
              Cancel
            </Button>
          </ComposerPrimitive.Cancel>
          <ComposerPrimitive.Send asChild>
            <Button size="sm" className="h-8 rounded-full px-3.5">
              Update
            </Button>
          </ComposerPrimitive.Send>
        </div>
      </ComposerPrimitive.Root>
    </MessagePrimitive.Root>
  );
};

const BranchPicker: FC<BranchPickerPrimitive.Root.Props> = ({
  className,
  ...rest
}) => {
  return (
    <BranchPickerPrimitive.Root
      hideWhenSingleBranch
      className={cn(
        "aui-branch-picker-root text-muted-foreground -ms-2 me-2 inline-flex items-center text-xs",
        className,
      )}
      {...rest}
    >
      <BranchPickerPrimitive.Previous asChild>
        <TooltipIconButton tooltip="上一条">
          <ChevronLeftIcon />
        </TooltipIconButton>
      </BranchPickerPrimitive.Previous>
      <span className="aui-branch-picker-state font-medium">
        <BranchPickerPrimitive.Number /> / <BranchPickerPrimitive.Count />
      </span>
      <BranchPickerPrimitive.Next asChild>
        <TooltipIconButton tooltip="下一条">
          <ChevronRightIcon />
        </TooltipIconButton>
      </BranchPickerPrimitive.Next>
    </BranchPickerPrimitive.Root>
  );
};
