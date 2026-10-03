"use client";

import { Eye, EyeOff } from "lucide-react";
import React, { useState } from "react";
import Input from "./Input";

type Props = Omit<React.ComponentProps<typeof Input>, "type" | "trailing">;

export default function PasswordInput(props: Props) {
  const [visible, setVisible] = useState(false);
  return (
    <Input
      {...props}
      type={visible ? "text" : "password"}
      trailing={
        <button type="button" onClick={() => setVisible((v) => !v)} aria-label={visible ? "Hide password" : "Show password"} className="rounded-lg p-2 text-text-light transition-colors hover:text-text-dark">
          {visible ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
        </button>
      }
    />
  );
}
