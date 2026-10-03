"use client";

import { Eye, EyeOff } from "lucide-react";
import React, { useState } from "react";
import { useI18n } from "@/lib/i18n/I18nProvider";
import Input from "./Input";

type Props = Omit<React.ComponentProps<typeof Input>, "type" | "trailing">;

export default function PasswordInput(props: Props) {
  const [visible, setVisible] = useState(false);
  const { t } = useI18n();
  return (
    <Input
      {...props}
      type={visible ? "text" : "password"}
      trailing={
        <button type="button" onClick={() => setVisible((v) => !v)} aria-label={visible ? t.login.hidePassword : t.login.showPassword} aria-pressed={visible}
          className="rounded-md p-2 text-text-light transition-colors hover:text-text-dark">
          {visible ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
        </button>
      }
    />
  );
}
