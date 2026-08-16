"use client";

import { useEffect, useState, useRef } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

export default function LessonChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [streamingContent, setStreamingContent] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const router = useRouter();
  const params = useParams();
  const lessonId = params?.id as string;

  useEffect(() => {
    const fetchMessages = async () => {
      const token = localStorage.getItem('access_token');
      const orgId = localStorage.getItem('active_org_id');
      
      if (!token || !orgId) {
        router.push('/login');
        return;
      }

      try {
        const res = await fetch(`http://localhost:8001/api/v1/organizations/${orgId}/lessons/${lessonId}/messages`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) {
          const data = await res.json();
          setMessages(data);
        }
      } catch (err: unknown) {
        if (err instanceof Error) {
          console.error(err.message);
        }
      } finally {
        setLoading(false);
      }
    };

    fetchMessages();
  }, [lessonId, router]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;
    
    const token = localStorage.getItem('access_token');
    const orgId = localStorage.getItem('active_org_id');
    const userMessageContent = input.trim();
    
    setInput('');
    setMessages(prev => [...prev, { id: 'temp-' + Date.now(), role: 'user', content: userMessageContent }]);
    setIsStreaming(true);
    setStreamingContent('');

    try {
      const res = await fetch(`http://localhost:8001/api/v1/organizations/${orgId}/lessons/${lessonId}/messages/stream`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ content: userMessageContent })
      });

      if (!res.ok) {
        if (res.status === 401) {
          localStorage.removeItem('access_token');
          router.push('/login');
          return;
        }
        throw new Error('Mesaj gönderilemedi');
      }
      if (!res.body) throw new Error('ReadableStream not supported');

      const reader = res.body.getReader();
      const decoder = new TextDecoder('utf-8');
      
      let aiContent = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        
        const chunkStr = decoder.decode(value, { stream: true });
        const lines = chunkStr.split('\n');
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.replace('data: ', '');
            if (dataStr.trim() === '') continue;
            
            try {
              const parsed = JSON.parse(dataStr);
              if (parsed.error) {
                console.error('Stream error:', parsed.error);
                break;
              }
              if (parsed.content) {
                aiContent += parsed.content;
                setStreamingContent(aiContent);
              }
              if (parsed.done) {
                // Done
              }
            } catch {
              // ignore parse errors for partial chunks
            }
          }
        }
      }

      setMessages(prev => [...prev, { id: 'temp-ai-' + Date.now(), role: 'assistant', content: aiContent }]);
      setStreamingContent('');

    } catch (err: unknown) {
      if (err instanceof Error) {
        console.error(err.message);
      }
    } finally {
      setIsStreaming(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const token = localStorage.getItem('access_token');
    const orgId = localStorage.getItem('active_org_id');
    
    if (!token || !orgId) return;

    setIsUploading(true);
    
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`http://localhost:8001/api/v1/organizations/${orgId}/resources`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      });

      if (!res.ok) {
        throw new Error('Dosya yüklenemedi.');
      }
      
      // Successfully uploaded
      setMessages(prev => [...prev, { 
        id: 'sys-' + Date.now(), 
        role: 'assistant', 
        content: `📄 "${file.name}" belgesi başarıyla yüklendi ve öğreniliyor. Artık bu belgeyle ilgili sorular sorabilirsiniz.` 
      }]);
    } catch (err: unknown) {
      if (err instanceof Error) {
        console.error(err.message);
        setMessages(prev => [...prev, { 
          id: 'err-' + Date.now(), 
          role: 'assistant', 
          content: `❌ Belge yükleme hatası: ${err.message}` 
        }]);
      }
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',
      background: 'var(--background)'
    }}>
      {/* Header */}
      <div style={{
        padding: '1rem 2rem',
        background: 'var(--surface)',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        gap: '1rem'
      }}>
        <Link href="/lessons" className="btn btn-secondary" style={{ padding: '0.5rem 1rem' }}>
          ← Geri
        </Link>
        <h2 style={{ fontSize: '1.25rem', margin: 0 }}>Canlı Ders Görüşmesi</h2>
      </div>

      {/* Chat Area */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '2rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '1.5rem',
        maxWidth: '900px',
        margin: '0 auto',
        width: '100%'
      }}>
        {loading && <p style={{ textAlign: 'center' }}>Yükleniyor...</p>}
        
        {!loading && messages.length === 0 && (
          <div className="card text-center" style={{ margin: 'auto' }}>
            <h3>Ders Başladı!</h3>
            <p>Konuyla ilgili bir soru sorarak veya analiz yapmak istediğiniz bir dokümanı belirterek başlayabilirsiniz.</p>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} style={{
            alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
            maxWidth: '80%',
            background: msg.role === 'user' ? 'var(--primary)' : 'var(--surface)',
            color: msg.role === 'user' ? 'white' : 'var(--foreground)',
            padding: '1rem 1.5rem',
            borderRadius: '1rem',
            borderBottomRightRadius: msg.role === 'user' ? '0' : '1rem',
            borderBottomLeftRadius: msg.role === 'assistant' ? '0' : '1rem',
            boxShadow: 'var(--shadow-sm)',
            border: msg.role === 'assistant' ? '1px solid var(--border)' : 'none'
          }}>
            <p style={{ margin: 0, whiteSpace: 'pre-wrap', color: 'inherit' }}>{msg.content}</p>
          </div>
        ))}

        {isStreaming && (
          <div style={{
            alignSelf: 'flex-start',
            maxWidth: '80%',
            background: 'var(--surface)',
            color: 'var(--foreground)',
            padding: '1rem 1.5rem',
            borderRadius: '1rem',
            borderBottomLeftRadius: '0',
            boxShadow: 'var(--shadow-sm)',
            border: '1px solid var(--border)'
          }}>
            <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
              {streamingContent}
              <span className="cursor" style={{ 
                display: 'inline-block', 
                width: '8px', 
                height: '16px', 
                background: 'var(--primary)', 
                marginLeft: '4px',
                animation: 'blink 1s step-start infinite' 
              }}></span>
            </p>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div style={{
        padding: '1.5rem 2rem',
        background: 'var(--surface)',
        borderTop: '1px solid var(--border)'
      }}>
        <form onSubmit={handleSendMessage} style={{
          display: 'flex',
          gap: '1rem',
          maxWidth: '900px',
          margin: '0 auto',
          alignItems: 'center'
        }}>
          <input 
            type="file" 
            ref={fileInputRef} 
            onChange={handleFileUpload} 
            style={{ display: 'none' }} 
            accept=".pdf,.txt,.docx,.md"
          />
          <button 
            type="button" 
            className="btn btn-secondary" 
            onClick={() => fileInputRef.current?.click()}
            disabled={isStreaming || isUploading}
            style={{ padding: '1rem', borderRadius: '50%', width: '3rem', height: '3rem', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
            title="Belge Yükle"
          >
            {isUploading ? '⏳' : '📎'}
          </button>
          
          <input
            type="text"
            className="input"
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Mesajınızı yazın..."
            disabled={isStreaming}
            style={{ flex: 1, padding: '1rem 1.5rem' }}
          />
          <button type="submit" className="btn btn-primary" disabled={isStreaming || !input.trim()} style={{ padding: '0 2rem' }}>
            Gönder
          </button>
        </form>
      </div>

      <style dangerouslySetInnerHTML={{__html: `
        @keyframes blink {
          50% { opacity: 0; }
        }
      `}} />
    </div>
  );
}
