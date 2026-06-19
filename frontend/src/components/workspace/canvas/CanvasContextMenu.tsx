/**
 * CanvasContextMenu — right-click menu for canvas nodes.
 * Options: Duplicate, Connect to, Delete.
 */

import { useEffect, useRef } from "react";
import { Copy, Link, Trash2 } from "lucide-react";

interface CanvasContextMenuProps {
  x: number;
  y: number;
  nodeId: string;
  onDuplicate: (nodeId: string) => void;
  onConnect: (nodeId: string) => void;
  onDelete: (nodeId: string) => void;
  onClose: () => void;
}

export function CanvasContextMenu({
  x,
  y,
  nodeId,
  onDuplicate,
  onConnect,
  onDelete,
  onClose,
}: CanvasContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [onClose]);

  const menuItems = [
    { label: "Duplicate", icon: Copy, action: () => onDuplicate(nodeId) },
    { label: "Connect to", icon: Link, action: () => onConnect(nodeId) },
    { label: "Delete", icon: Trash2, action: () => onDelete(nodeId), destructive: true },
  ];

  return (
    <div
      ref={menuRef}
      className="fixed z-50 min-w-[140px] rounded-md border bg-popover p-1 shadow-md"
      style={{ left: x, top: y }}
    >
      {menuItems.map((item) => (
        <button
          key={item.label}
          className={`flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm transition-colors hover:bg-accent ${
            item.destructive ? "text-red-500 hover:text-red-600" : "text-popover-foreground"
          }`}
          onClick={() => {
            item.action();
            onClose();
          }}
        >
          <item.icon className="h-3.5 w-3.5" />
          {item.label}
        </button>
      ))}
    </div>
  );
}

export default CanvasContextMenu;
