"use client";

import { useState, useRef, useEffect } from "react";
import { api } from "@/lib/api";
import { MessageSquare, Send, X, Bot, User, Loader2 } from "lucide-react";

interface Message {
  role: "user" | "assistant";
  content: string;
  sql?: string;
  timestamp: Date;
}

export default function AssistantChat() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Hola, soy el Vision Assistant. Preguntame sobre las detecciones, camaras o personas. Por ejemplo:\n\n- Cuantas personas se detectaron hoy?\n- Que camaras estan en linea?\n- Quien trajo casco hoy?",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const question = input.trim();
    setInput("");

    // Add user message
    setMessages((prev) => [
      ...prev,
      { role: "user", content: question, timestamp: new Date() },
    ]);

    setLoading(true);

    try {
      const response = await api.askAssistant(question);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: response.answer || "No obtuve respuesta.",
          sql: response.sql,
          timestamp: new Date(),
        },
      ]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Error: ${err.message || "No se pudo conectar con el asistente."}`,
          timestamp: new Date(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {/* Floating Button */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="fixed bottom-6 right-6 w-14 h-14 bg-primary hover:bg-primary-hover rounded-full flex items-center justify-center shadow-lg shadow-primary/20 transition-all z-50 group"
        >
          <MessageSquare className="w-6 h-6 text-white" />
          <span className="absolute -top-8 right-0 bg-surface border border-border text-text-secondary text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
            Vision Assistant
          </span>
        </button>
      )}

      {/* Chat Panel */}
      {isOpen && (
        <div className="fixed bottom-6 right-6 w-96 h-[32rem] bg-surface border border-border rounded-2xl shadow-2xl flex flex-col z-50 overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-surface">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                <Bot className="w-4 h-4 text-primary" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-text-primary">
                  Vision Assistant
                </h3>
                <p className="text-[10px] text-text-muted">Phi-3 Mini | Local</p>
              </div>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="p-1.5 rounded-lg hover:bg-surface-hover transition-colors"
            >
              <X className="w-4 h-4 text-text-muted" />
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex gap-2 ${
                  msg.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                {msg.role === "assistant" && (
                  <div className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
                    <Bot className="w-3 h-3 text-primary" />
                  </div>
                )}
                <div
                  className={`max-w-[80%] rounded-xl px-3 py-2 text-sm ${
                    msg.role === "user"
                      ? "bg-primary text-white"
                      : "bg-background text-text-primary"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                  {msg.sql && (
                    <details className="mt-2">
                      <summary className="text-[10px] text-text-muted cursor-pointer hover:text-text-secondary">
                        Ver SQL
                      </summary>
                      <pre className="mt-1 text-[10px] text-text-muted font-mono bg-surface p-2 rounded overflow-x-auto">
                        {msg.sql}
                      </pre>
                    </details>
                  )}
                </div>
                {msg.role === "user" && (
                  <div className="w-6 h-6 rounded-full bg-accent/10 flex items-center justify-center shrink-0 mt-0.5">
                    <User className="w-3 h-3 text-accent" />
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center">
                  <Bot className="w-3 h-3 text-primary" />
                </div>
                <div className="bg-background rounded-xl px-3 py-2">
                  <Loader2 className="w-4 h-4 text-primary animate-spin" />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <form
            onSubmit={handleSubmit}
            className="border-t border-border p-3 flex gap-2"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Pregunta sobre detecciones..."
              disabled={loading}
              className="flex-1 px-3 py-2 bg-background border border-border rounded-lg text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="p-2 bg-primary hover:bg-primary-hover text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      )}
    </>
  );
}
