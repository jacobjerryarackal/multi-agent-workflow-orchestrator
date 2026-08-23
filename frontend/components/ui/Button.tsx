import React from "react";
import { cn } from "@/lib/utils/cn";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger" | "ghost" | "outline";
  size?: "sm" | "md" | "lg" | "icon";
  isLoading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = "secondary",
      size = "md",
      isLoading = false,
      disabled,
      children,
      ...props
    },
    ref
  ) => {
    const variantStyles = {
      primary:
        "bg-zinc-100 text-zinc-900 hover:bg-white active:bg-zinc-200 border-zinc-200 shadow-sm",
      secondary:
        "bg-zinc-800/80 text-zinc-200 hover:bg-zinc-700/80 active:bg-zinc-800 border-zinc-700/80",
      danger:
        "bg-rose-950 text-rose-200 hover:bg-rose-900 border-rose-800/80 active:bg-rose-950",
      ghost:
        "bg-transparent text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800/60 border-transparent",
      outline:
        "bg-transparent text-zinc-300 hover:bg-zinc-800/40 border-zinc-700 hover:text-zinc-100",
    };

    const sizeStyles = {
      sm: "h-7 px-2.5 text-xs gap-1.5",
      md: "h-8 px-3 text-xs gap-2",
      lg: "h-9 px-4 text-sm gap-2",
      icon: "h-8 w-8 p-0 justify-center",
    };

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={cn(
          "inline-flex items-center justify-center font-medium rounded border transition-colors select-none focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-zinc-400 disabled:opacity-50 disabled:pointer-events-none cursor-pointer",
          variantStyles[variant],
          sizeStyles[size],
          className
        )}
        {...props}
      >
        {isLoading ? (
          <span className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin shrink-0" />
        ) : null}
        {children}
      </button>
    );
  }
);

Button.displayName = "Button";
