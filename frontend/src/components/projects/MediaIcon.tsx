/**
 * MediaIcon — Renders an icon + label representing the media type of a task.
 */

import { Video, Image, AudioLines, FileText } from "lucide-react";
import type { MediaType } from "./types";

interface MediaIconProps {
  mediaType: MediaType;
}

const MEDIA_CONFIG: Record<MediaType, { icon: React.ElementType; label: string }> = {
  video: { icon: Video, label: "Video" },
  image: { icon: Image, label: "Image" },
  audio: { icon: AudioLines, label: "Audio" },
  text: { icon: FileText, label: "Text" },
};

export function MediaIcon({ mediaType }: MediaIconProps) {
  const config = MEDIA_CONFIG[mediaType];
  const Icon = config.icon;

  return (
    <div className="flex items-center gap-2">
      <Icon size={16} className="text-text-caption" />
      <span className="text-label-ui text-text-body">{config.label}</span>
    </div>
  );
}
