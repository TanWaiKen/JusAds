import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { TEMPLATE_CONFIGS, type TemplateType } from "@/types/easyGeneration";

// ─── Props ───────────────────────────────────────────────────────────────────

interface DynamicFormProps {
  selectedTemplate: TemplateType;
  formValues: Record<string, string>;
  onFormChange: (values: Record<string, string>) => void;
}

// ─── Constants ───────────────────────────────────────────────────────────────

const FIELD_LABELS: Record<string, string> = {
  product_name: "Product / Brand Name",
  key_message: "Key Message",
  target_audience: "Target Audience",
  platform: "Platform",
  brand_tone: "Brand Tone / Style",
  visual_style: "Visual Style",
  color_palette: "Color Palette",
  slide_count: "Number of Slides",
  copy_length: "Copy Length",
  call_to_action: "Call to Action",
  language: "Language",
};

const FIELD_PLACEHOLDERS: Record<string, string> = {
  product_name: "Nasi Lemak Warung",
  key_message: "Raya promotion — 30% off all items",
  target_audience: "Malay audience 25-40",
  brand_tone: "Warm, festive, family-friendly",
  platform: "Instagram",
  visual_style: "Colorful, food photography",
  color_palette: "Red and gold",
  slide_count: "5",
  copy_length: "Short (< 100 words)",
  call_to_action: "Order Now on WhatsApp",
  language: "Bahasa Melayu",
};

const REQUIRED_FIELDS = new Set(["product_name", "key_message"]);

const MARKET_OPTIONS = [
  { value: "malaysia", label: "Malaysia" },
  { value: "singapore", label: "Singapore" },
];

const ETHNICITY_OPTIONS = [
  { value: "malay", label: "Malay" },
  { value: "chinese", label: "Chinese" },
  { value: "indian", label: "Indian" },
  { value: "all", label: "All" },
];

const AGE_GROUP_OPTIONS = [
  { value: "gen_z", label: "Gen Z" },
  { value: "millennial", label: "Millennial" },
  { value: "gen_x", label: "Gen X" },
  { value: "baby_boomer", label: "Baby Boomer" },
  { value: "all", label: "All" },
];

// ─── Component ───────────────────────────────────────────────────────────────

export function DynamicForm({
  selectedTemplate,
  formValues,
  onFormChange,
}: DynamicFormProps) {
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  const config = TEMPLATE_CONFIGS[selectedTemplate];
  const allFields = [...config.fields.common, ...config.fields.specific];

  function handleFieldChange(field: string, value: string) {
    onFormChange({ ...formValues, [field]: value });
  }

  function handleBlur(field: string) {
    setTouched((prev) => ({ ...prev, [field]: true }));
  }

  function isFieldInvalid(field: string): boolean {
    return REQUIRED_FIELDS.has(field) && touched[field] === true && !formValues[field]?.trim();
  }

  function handleSelectChange(field: string, value: string | null) {
    if (value) {
      onFormChange({ ...formValues, [field]: value });
    }
  }

  return (
    <div className="space-y-4">
      {/* Dynamic template fields */}
      {allFields.map((field) => (
        <div key={field} className="space-y-1.5">
          <Label htmlFor={`field-${field}`}>
            {FIELD_LABELS[field] ?? field}
            {REQUIRED_FIELDS.has(field) && (
              <span className="text-destructive ml-1">*</span>
            )}
          </Label>
          <Input
            id={`field-${field}`}
            value={formValues[field] ?? ""}
            placeholder={FIELD_PLACEHOLDERS[field] ?? ""}
            onChange={(e) => handleFieldChange(field, e.target.value)}
            onBlur={() => handleBlur(field)}
            aria-required={REQUIRED_FIELDS.has(field)}
            aria-invalid={isFieldInvalid(field)}
            className={isFieldInvalid(field) ? "border-destructive" : ""}
          />
          {isFieldInvalid(field) && (
            <p className="text-xs text-destructive">
              {FIELD_LABELS[field] ?? field} is required
            </p>
          )}
        </div>
      ))}

      {/* Target Nation selector */}
      <div className="space-y-1.5">
        <Label htmlFor="field-market">Target Nation</Label>
        <Select
          value={formValues.market ?? "malaysia"}
          onValueChange={(v) => handleSelectChange("market", v)}
        >
          <SelectTrigger className="w-full" id="field-market">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {MARKET_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Target Audience section */}
      <div className="space-y-3">
        <Label className="text-sm font-medium">Target Audience</Label>

        <div className="grid grid-cols-2 gap-3">
          {/* Ethnicity */}
          <div className="space-y-1.5">
            <Label htmlFor="field-ethnicity" className="text-xs text-muted-foreground">
              Ethnicity
            </Label>
            <Select
              value={formValues.target_ethnicity ?? "all"}
              onValueChange={(v) => handleSelectChange("target_ethnicity", v)}
            >
              <SelectTrigger className="w-full" id="field-ethnicity">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ETHNICITY_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Age Group */}
          <div className="space-y-1.5">
            <Label htmlFor="field-age-group" className="text-xs text-muted-foreground">
              Age Group
            </Label>
            <Select
              value={formValues.age_group ?? "all"}
              onValueChange={(v) => handleSelectChange("age_group", v)}
            >
              <SelectTrigger className="w-full" id="field-age-group">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {AGE_GROUP_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>
    </div>
  );
}
