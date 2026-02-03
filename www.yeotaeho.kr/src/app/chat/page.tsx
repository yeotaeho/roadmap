"use client";

import React, { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import { Bot } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { MessageBubble } from '@/components/features/chat/MessageBubble';
import { ChatInput } from '@/components/features/chat/ChatInput';

interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
}

export default function ChatPage() {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [chatMode, setChatMode] = useState<'trend' | 'career'>('trend');
    const messagesEndRef = useRef<HTMLDivElement>(null);

    // 스크롤을 맨 아래로
    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    // 초기 환영 메시지는 표시하지 않음 (이미지 스타일 참고)

    // AI 응답 생성 (Mock)
    const generateResponse = async (userMessage: string, mode: 'trend' | 'career'): Promise<string> => {
        // 실제로는 API 호출
        await new Promise(resolve => setTimeout(resolve, 1000 + Math.random() * 1000));

        const trendResponses = [
            "미래 트렌드 분석에 따르면, AI와 머신러닝 기술이 계속해서 성장할 것으로 예상됩니다. 특히 생성형 AI와 자율주행 기술이 주목받고 있어요.",
            "환경 친화적인 기술과 지속가능한 에너지 솔루션이 미래의 핵심 트렌드가 될 것 같습니다. ESG 경영이 기업의 필수 요소가 되고 있어요.",
            "디지털 헬스케어와 원격 의료 서비스가 빠르게 발전하고 있습니다. 특히 웨어러블 디바이스와 AI 진단 기술이 결합되면서 새로운 시장이 형성되고 있어요.",
            "메타버스와 가상현실 기술이 교육, 엔터테인먼트, 비즈니스 등 다양한 분야에서 활용되고 있습니다. 향후 5년 내 일상생활의 일부가 될 것으로 예상됩니다.",
        ];

        const careerResponses = [
            "진로 상담을 위해 몇 가지 질문을 드릴게요. 현재 관심 있는 분야나 전공이 있나요? 그리고 어떤 가치를 중요하게 생각하시나요?",
            "자신의 강점과 관심사를 파악하는 것이 진로 선택의 첫 단계입니다. 어떤 활동을 할 때 가장 즐거움을 느끼시나요?",
            "미래 직업 시장을 고려할 때, 기술과 창의성을 결합한 분야가 유망합니다. 데이터 분석, AI, 디지털 마케팅 등이 성장하고 있어요.",
            "진로는 한 번에 결정되는 것이 아니라 점진적으로 발전해 나가는 과정입니다. 다양한 경험을 쌓아가며 자신만의 길을 찾아가시길 바라요.",
        ];

        const responses = mode === 'trend' ? trendResponses : careerResponses;
        return responses[Math.floor(Math.random() * responses.length)];
    };

    const handleSend = async () => {
        if (!input.trim() || isLoading) return;

        const userMessage: Message = {
            id: Date.now().toString(),
            role: 'user',
            content: input.trim(),
            timestamp: new Date(),
        };

        setMessages(prev => [...prev, userMessage]);
        setInput('');
        setIsLoading(true);

        try {
            const response = await generateResponse(userMessage.content, chatMode);
            const assistantMessage: Message = {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: response,
                timestamp: new Date(),
            };
            setMessages(prev => [...prev, assistantMessage]);
        } catch (error) {
            console.error('Error generating response:', error);
        } finally {
            setIsLoading(false);
        }
    };

    const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const switchMode = (mode: 'trend' | 'career') => {
        setChatMode(mode);
        setMessages([]);
        setInput('');
    };

    const resetChat = () => {
        setMessages([]);
        setInput('');
    };

    const hasMessages = messages.length > 0;

    return (
        <div className="min-h-screen bg-white flex flex-col">
            {/* Header */}
            <header className="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-50">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
                    <div className="flex items-center justify-between">
                        <Link href="/" className="text-xl font-extrabold text-gray-800">
                            SAMSUNG <span className="font-normal text-sm block -mt-1">Newsroom</span>
                        </Link>
                        <div className="flex items-center gap-4">
                            {/* Mode Switch Buttons */}
                            <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
                                <button
                                    onClick={() => switchMode('trend')}
                                    className={`px-3 py-1 rounded text-sm transition ${chatMode === 'trend'
                                        ? 'bg-white text-gray-900 font-medium shadow-sm'
                                        : 'text-gray-600 hover:text-gray-900'
                                        }`}
                                >
                                    트렌드
                                </button>
                                <button
                                    onClick={() => switchMode('career')}
                                    className={`px-3 py-1 rounded text-sm transition ${chatMode === 'career'
                                        ? 'bg-white text-gray-900 font-medium shadow-sm'
                                        : 'text-gray-600 hover:text-gray-900'
                                        }`}
                                >
                                    진로
                                </button>
                            </div>
                            <Link
                                href="/"
                                className="px-4 py-2 text-sm text-gray-700 hover:text-red-600 transition font-medium"
                            >
                                ← 메인으로
                            </Link>
                        </div>
                    </div>
                </div>
            </header>

            {/* Main Content */}
            <div className="flex-1 flex flex-col max-w-4xl mx-auto w-full px-4 sm:px-6 lg:px-8">
                {!hasMessages ? (
                    /* Empty State - 이미지 스타일 */
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="flex-1 flex flex-col items-center justify-center py-20"
                    >
                        <h1 className="text-2xl font-semibold text-gray-900 mb-12">
                            무엇을 도와 드릴까요?
                        </h1>

                        {/* Input Bar */}
                        <div className="w-full max-w-2xl">
                            <ChatInput
                                value={input}
                                onChange={setInput}
                                onSend={handleSend}
                                disabled={isLoading}
                            />
                        </div>
                    </motion.div>
                ) : (
                    /* Chat Area - 메시지가 있을 때 */
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="flex-1 flex flex-col"
                    >
                        {/* Messages */}
                        <div className="flex-1 overflow-y-auto p-6 space-y-4">
                            {messages.map((message) => (
                                <MessageBubble key={message.id} message={message} />
                            ))}

                            {isLoading && (
                                <motion.div
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    className="flex gap-3 justify-start"
                                >
                                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center flex-shrink-0">
                                        <Bot className="w-5 h-5 text-white" />
                                    </div>
                                    <div className="bg-gray-100 rounded-lg px-4 py-3">
                                        <div className="flex gap-1">
                                            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                                            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                                            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                                        </div>
                                    </div>
                                </motion.div>
                            )}
                            <div ref={messagesEndRef} />
                        </div>

                        {/* Input Area */}
                        <div className="border-t border-gray-200 p-4 bg-white">
                            <ChatInput
                                value={input}
                                onChange={setInput}
                                onSend={handleSend}
                                disabled={isLoading}
                            />
                        </div>
                    </motion.div>
                )}
            </div>
        </div>
    );
}

