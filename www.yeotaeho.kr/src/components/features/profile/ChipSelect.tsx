// 칩/세그먼트 선택 — 택1(multi=false) 또는 다중(multi=true)

"use client";

import { Option } from "@/data/personalizationOptions";

interface Props {
  options: Option[];
  value: string | string[] | null;
  multi?: boolean;
  onChange: (value: string | string[]) => void;
}

export default function ChipSelect({ options, value, multi = false, onChange }: Props) {
  const selected = (v: string) => (multi ? Array.isArray(value) && value.includes(v) : value === v);

  const toggle = (v: string) => {
    if (multi) {
      const cur = Array.isArray(value) ? value : [];
      onChange(cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v]);
    } else {
      onChange(value === v ? "" : v);
    }
  };

  return (
    <div className="flex flex-wrap gap-2">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => toggle(o.value)}
          className={`px-3 py-1.5 rounded-full text-sm border transition ${
            selected(o.value)
              ? "border-red-600 bg-red-600 text-white"
              : "border-gray-300 bg-white text-gray-700 hover:border-gray-400"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
