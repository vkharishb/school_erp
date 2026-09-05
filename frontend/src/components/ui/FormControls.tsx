import type { HTMLInputTypeAttribute } from "react";

type Option = readonly [string, string];

export function FormField({
  label,
  value,
  onChange,
  type = "text",
  required = true,
  disabled = false,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: HTMLInputTypeAttribute;
  required?: boolean;
  disabled?: boolean;
  placeholder?: string;
}) {
  return <label>
    <span className="label">{label}</span>
    <input
      className="input disabled:bg-gray-100"
      type={type}
      value={value}
      onChange={event => onChange(event.target.value)}
      required={required}
      disabled={disabled}
      placeholder={placeholder}
    />
  </label>;
}

export function FormSelect({
  label,
  value,
  onChange,
  options,
  required = true,
  placeholder = "Select",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: readonly Option[];
  required?: boolean;
  placeholder?: string;
}) {
  return <label>
    <span className="label">{label}</span>
    <select className="input" value={value} onChange={event => onChange(event.target.value)} required={required}>
      <option value="">{placeholder}</option>
      {options.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
    </select>
  </label>;
}

export function StatusAlert({kind, text}: {kind: "error" | "success"; text: string}) {
  const colors = kind === "error"
    ? "border-red-200 bg-red-50 text-red-700"
    : "border-green-200 bg-green-50 text-green-700";
  return <div className={`rounded-lg border px-4 py-3 text-sm ${colors}`}>{text}</div>;
}
