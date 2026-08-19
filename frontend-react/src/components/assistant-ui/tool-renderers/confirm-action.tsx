"use client";

import { type FC, useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { AlertTriangle } from "lucide-react";
import { useChatSend } from "@/components/assistant-ui/aisdk-runtime-provider";

interface ConfirmField {
  name: string;
  label: string;
  type: "text" | "email" | "select";
  required: boolean;
  placeholder?: string;
  options?: string[];
  default?: string;
}

interface ConfirmEntities {
  title?: string;
  fields?: ConfirmField[];
  danger?: boolean;
}

interface ConfirmActionRendererProps {
  args: {
    action?: string;
    entities?: ConfirmEntities;
  };
  approval?: { approved?: boolean };
  respondToApproval?: (response: { approved: boolean; reason?: string }) => void;
  result?: unknown;
}

export const ConfirmActionRenderer: FC<ConfirmActionRendererProps> = ({
  args,
  approval,
  respondToApproval,
  result,
}) => {
  const { sendMessage } = useChatSend();

  // Initialize form values from field defaults
  const [formValues, setFormValues] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    args.entities?.fields?.forEach((f) => {
      initial[f.name] = f.default || "";
    });
    return initial;
  });

  const updateField = useCallback((name: string, value: string) => {
    setFormValues((prev) => ({ ...prev, [name]: value }));
  }, []);

  const fields = args.entities?.fields;
  const hasForm = fields && fields.length > 0;

  // Waiting for user decision
  if (approval?.approved === undefined && result === undefined) {
    const danger = args.entities?.danger;
    const title = args.entities?.title || args.action || "确认操作";

    return (
      <Card className={danger ? "border-red-200 bg-red-50" : "border-amber-200 bg-amber-50"}>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <AlertTriangle className={danger ? "h-5 w-5 text-red-600" : "h-5 w-5 text-amber-600"} />
            {title}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {hasForm ? (
            <div className="flex flex-col gap-3">
              {fields!.map((field) => (
                <div key={field.name} className="flex flex-col gap-1">
                  <Label className="text-xs font-medium">
                    {field.label}
                    {field.required && <span className="text-red-500 ml-0.5">*</span>}
                  </Label>
                  {field.type === "select" ? (
                    <Select
                      value={formValues[field.name]}
                      onValueChange={(v) => updateField(field.name, v)}
                    >
                      <SelectTrigger className="h-9">
                        <SelectValue placeholder={field.placeholder || `选择${field.label}`} />
                      </SelectTrigger>
                      <SelectContent>
                        {field.options?.map((opt) => (
                          <SelectItem key={opt} value={opt}>{opt}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <Input
                      type={field.type}
                      value={formValues[field.name]}
                      onChange={(e) => updateField(field.name, e.target.value)}
                      placeholder={field.placeholder}
                      className="h-9"
                    />
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm">{args.action || "是否执行此操作？"}</p>
          )}
        </CardContent>
        <CardFooter className="flex gap-2">
          <Button
            size="sm"
            variant={danger ? "destructive" : "default"}
            disabled={hasForm && fields!.some((f) => f.required && !formValues[f.name])}
            onClick={() => {
              respondToApproval?.({ approved: true });
              if (hasForm) {
                const fieldStr = fields!
                  .map((f) => `${f.label}: ${formValues[f.name]}`)
                  .join("，");
                sendMessage(`✅ 确认操作：\n\n${fieldStr}`);
              } else {
                sendMessage("✅ 确认操作：");
              }
            }}
          >
            确认提交
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              respondToApproval?.({ approved: false, reason: "用户取消" });
              sendMessage("取消操作：");
            }}
          >
            取消
          </Button>
        </CardFooter>
      </Card>
    );
  }

  if (approval?.approved === false) {
    return <div className="text-sm text-muted-foreground p-3">操作已取消。</div>;
  }
  if (result === undefined) {
    return <div className="text-sm text-muted-foreground p-3">操作已确认，正在执行...</div>;
  }
  return (
    <div className="text-sm p-3">
      <div className="text-xs text-muted-foreground mb-1">操作完成</div>
      <pre className="whitespace-pre-wrap break-words text-xs bg-muted rounded p-2">
        {JSON.stringify(result, null, 2)}
      </pre>
    </div>
  );
};