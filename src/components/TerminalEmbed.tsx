import { useEffect, useRef, useState } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import '@xterm/xterm/css/xterm.css';

interface TerminalEmbedProps {
  sandboxId: string;
  visible: boolean;
}

export function TerminalEmbed({ sandboxId, visible }: TerminalEmbedProps) {
  const termRef = useRef<HTMLDivElement>(null);
  const terminalRef = useRef<Terminal | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!visible || !sandboxId || !termRef.current) return;

    const terminal = new Terminal({
      cursorBlink: true,
      fontSize: 13,
      fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace',
      theme: {
        background: '#18181b',
        foreground: '#d4d4d8',
        cursor: '#14b8a6',
        selectionBackground: '#2dd4bf33',
      },
      scrollback: 5000,
      convertEol: true,
    });

    const fitAddon = new FitAddon();
    const webLinksAddon = new WebLinksAddon();
    terminal.loadAddon(fitAddon);
    terminal.loadAddon(webLinksAddon);

    terminal.open(termRef.current);
    fitAddon.fit();

    terminalRef.current = terminal;
    fitAddonRef.current = fitAddon;

    // Connect WebSocket to the sandbox terminal relay.
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/admin/api/sandboxes/${sandboxId}/terminal?token=`;

    const ws = new WebSocket(wsUrl);
    ws.binaryType = 'arraybuffer';
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
    };

    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        terminal.write(new Uint8Array(event.data));
      } else {
        terminal.write(event.data);
      }
    };

    ws.onclose = () => {
      setConnected(false);
      terminal.write('\r\n\x1b[90m--- Terminal disconnected ---\x1b[0m\r\n');
    };

    ws.onerror = () => {
      setConnected(false);
    };

    // Forward terminal input to the WebSocket.
    const onDataDisposable = terminal.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(new TextEncoder().encode(data));
      }
    });

    // Forward binary input (e.g. paste with special chars).
    const onBinaryDisposable = terminal.onBinary((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        const bytes = new Uint8Array(data.length);
        for (let i = 0; i < data.length; i++) {
          bytes[i] = data.charCodeAt(i);
        }
        ws.send(bytes);
      }
    });

    // Send resize events when the terminal dimensions change.
    const onResizeDisposable = terminal.onResize(({ cols, rows }) => {
      if (ws.readyState === WebSocket.OPEN) {
        const resizeMsg = JSON.stringify({ type: 'resize', cols, rows });
        ws.send(new TextEncoder().encode(resizeMsg));
      }
    });

    // Handle container resize.
    const resizeObserver = new ResizeObserver(() => {
      fitAddon.fit();
    });
    resizeObserver.observe(termRef.current);

    return () => {
      onDataDisposable.dispose();
      onBinaryDisposable.dispose();
      onResizeDisposable.dispose();
      resizeObserver.disconnect();
      ws.close();
      wsRef.current = null;
      terminal.dispose();
      terminalRef.current = null;
      fitAddonRef.current = null;
    };
  }, [visible, sandboxId]);

  if (!visible) return null;

  return (
    <div className="mt-4">
      <div className="flex items-center gap-2 mb-2">
        <div
          className={`w-2 h-2 rounded-full ${connected ? 'bg-teal-400' : 'bg-zinc-500'}`}
        />
        <span className="text-xs text-zinc-400">
          {connected ? 'Connected' : 'Disconnected'}
        </span>
      </div>
      <div
        ref={termRef}
        className="bg-[#18181b] rounded-lg p-1 h-64 overflow-hidden"
      />
    </div>
  );
}
