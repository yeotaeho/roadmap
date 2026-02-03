import React, { useRef } from 'react';
import { Plus, Mic, Volume2 } from 'lucide-react';

interface ChatInputProps {
    value: string;
    onChange: (value: string) => void;
    onSend: () => void;
    placeholder?: string;
    disabled?: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({
    value,
    onChange,
    onSend,
    placeholder = '무엇이든 물어보세요',
    disabled = false,
}) => {
    const inputRef = useRef<HTMLInputElement>(null);

    const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === 'Enter' && !disabled) {
            e.preventDefault();
            onSend();
        }
    };

    return (
        <div className="relative flex items-center bg-white border border-gray-300 rounded-full px-4 py-3 shadow-sm hover:shadow-md transition-shadow">
            {/* Left Icon - Plus */}
            <button className="p-2 text-gray-600 hover:text-gray-900 transition">
                <Plus className="w-5 h-5" />
            </button>

            {/* Input Field */}
            <input
                ref={inputRef}
                type="text"
                value={value}
                onChange={(e) => onChange(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder={placeholder}
                disabled={disabled}
                className="flex-1 px-4 outline-none text-gray-900 placeholder-gray-400"
            />

            {/* Right Icons */}
            <div className="flex items-center gap-2">
                <button className="p-2 text-gray-600 hover:text-gray-900 transition">
                    <Mic className="w-5 h-5" />
                </button>
                <button className="p-2 text-gray-600 hover:text-gray-900 transition">
                    <Volume2 className="w-5 h-5" />
                </button>
            </div>
        </div>
    );
};

