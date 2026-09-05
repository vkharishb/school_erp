import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";

type Props = {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  autoComplete?: string;
  required?: boolean;
  minLength?: number;
  disabled?: boolean;
  className?: string;
};

export default function PasswordInput({
  id, value, onChange, placeholder, autoComplete = "new-password", required = true,
  minLength, disabled = false, className = "input",
}: Props) {
  const [visible, setVisible] = useState(false);
  return <div className="relative">
    <input
      id={id}
      type={visible ? "text" : "password"}
      className={`${className} pr-11`}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      autoComplete={autoComplete}
      required={required}
      minLength={minLength}
      disabled={disabled}
    />
    <button
      type="button"
      className="absolute inset-y-0 right-0 px-3 flex items-center text-gray-500 hover:text-gray-800"
      onClick={() => setVisible((current) => !current)}
      aria-label={visible ? "Hide password" : "Show password"}
      title={visible ? "Hide password" : "Show password"}
      disabled={disabled}
    >
      {visible ? <EyeOff size={18}/> : <Eye size={18}/>}
    </button>
  </div>;
}
