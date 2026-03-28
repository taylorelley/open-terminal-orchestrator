import { useEffect, useRef, useState } from 'react';

interface TerminalEmbedProps {
  sandboxId: string;
  visible: boolean;
}

export function TerminalEmbed({ sandboxId, visible }: TerminalEmbedProps) {
  const termRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [output, setOutput] = useState<string[]>([]);
  const [input, setInput] = useState('');

  useEffect(() => {
    if (!visible || !sandboxId) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/admin/api/sandboxes/${sandboxId}/terminal?token=`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        setOutput((prev) => [...prev, '--- Terminal connected ---']);
      };

      ws.onmessage = (event) => {
        setOutput((prev) => [...prev, event.data]);
      };

      ws.onclose = () => {
        setConnected(false);
        setOutput((prev) => [...prev, '--- Terminal disconnected ---']);
      };

      ws.onerror = () => {
        setConnected(false);
        setOutput((prev) => [...prev, '--- Connection error ---']);
      };
    } catch {
      setOutput((prev) => [...prev, '--- Failed to connect ---']);
    }

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [visible, sandboxId]);

  useEffect(() => {
    if (termRef.current) {
      termRef.current.scrollTop = termRef.current.scrollHeight;
    }
  }, [output]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN && input.trim()) {
      wsRef.current.send(input);
      setOutput((prev) => [...prev, `$ ${input}`]);
      setInput('');
    }
  };

  if (!visible) return null;

  return (
    <div className="mt-4">
      <div
        ref={termRef}
        className="bg-zinc-900 rounded-lg p-3 h-48 overflow-y-auto font-mono text-xs leading-relaxed"
      >
        {output.length === 0 ? (
          <span className="text-zinc-500">Connecting to sandbox terminal...</span>
        ) : (
          output.map((line, i) => (
            <div key={i} className="text-zinc-300 whitespace-pre-wrap">{line}</div>
          ))
        )}
      </div>
      <form onSubmit={handleSubmit} className="mt-2 flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={connected ? 'Type a command...' : 'Disconnected'}
          disabled={!connected}
          className="flex-1 px-3 py-1.5 bg-zinc-900 border border-zinc-700 rounded-lg text-sm text-zinc-300 font-mono focus:outline-none focus:ring-2 focus:ring-teal-500/20 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={!connected}
          className="px-3 py-1.5 bg-teal-600 hover:bg-teal-500 text-white text-xs font-medium rounded-lg transition-colors disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </div>
  );
}
