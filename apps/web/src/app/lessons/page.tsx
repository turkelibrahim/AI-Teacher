"use client";

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

interface Lesson {
  id: string;
  title: string;
  created_at: string;
  status: string;
}

export default function LessonsPage() {
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [newTitle, setNewTitle] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const fetchLessons = async () => {
      const token = localStorage.getItem('access_token');
      const orgId = localStorage.getItem('active_org_id');
      
      if (!token || !orgId) {
        router.push('/login');
        return;
      }

      try {
        const res = await fetch(`http://localhost:8001/api/v1/organizations/${orgId}/lessons`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });

        if (!res.ok) throw new Error('Dersler alınamadı.');
        const data = await res.json();
        setLessons(data);
      } catch (err: unknown) {
        if (err instanceof Error) {
          setError(err.message);
        }
      } finally {
        setLoading(false);
      }
    };

    fetchLessons();
  }, [router]);

  const handleCreateLesson = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;
    
    const token = localStorage.getItem('access_token');
    const orgId = localStorage.getItem('active_org_id');
    setIsCreating(true);

    try {
      const res = await fetch(`http://localhost:8001/api/v1/organizations/${orgId}/lessons`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ title: newTitle, status: 'ACTIVE' })
      });

      if (!res.ok) throw new Error('Ders oluşturulamadı.');
      
      const newLesson = await res.json();
      router.push(`/lessons/${newLesson.id}`);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      }
      setIsCreating(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      padding: '2rem',
      background: 'var(--background)'
    }}>
      <div style={{ maxWidth: '900px', margin: '0 auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
          <div>
            <Link href="/organizations" style={{ color: 'var(--primary)', fontSize: '0.875rem', fontWeight: 600 }}>
              ← Organizasyonlara Dön
            </Link>
            <h2 style={{ marginTop: '0.5rem' }}>Derslerim</h2>
          </div>
        </div>

        {error && <div style={{ color: 'var(--error)', marginBottom: '1rem' }}>{error}</div>}

        <div className="card" style={{ marginBottom: '2rem' }}>
          <h3 style={{ fontSize: '1.125rem', marginBottom: '1rem' }}>Yeni Ders Başlat</h3>
          <form onSubmit={handleCreateLesson} style={{ display: 'flex', gap: '1rem' }}>
            <input 
              type="text" 
              className="input" 
              placeholder="Ders Başlığı (Örn: Newton Kanunları)" 
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              required
            />
            <button type="submit" className="btn btn-primary" disabled={isCreating} style={{ whiteSpace: 'nowrap' }}>
              {isCreating ? 'Başlatılıyor...' : '+ Yeni Ders'}
            </button>
          </form>
        </div>
        
        {loading ? (
          <p>Dersler yükleniyor...</p>
        ) : lessons.length === 0 ? (
          <p style={{ color: '#64748b' }}>Henüz bir dersiniz bulunmuyor. Yukarıdan yeni bir ders başlatabilirsiniz.</p>
        ) : (
          <div style={{ display: 'grid', gap: '1rem' }}>
            {lessons.map((lesson) => (
              <Link key={lesson.id} href={`/lessons/${lesson.id}`}>
                <div className="card animate-fade-in" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem 1.5rem', cursor: 'pointer' }}>
                  <div>
                    <h3 style={{ fontSize: '1.125rem', marginBottom: '0.25rem' }}>{lesson.title}</h3>
                    <p style={{ fontSize: '0.875rem', color: '#64748b', margin: 0 }}>
                      Oluşturulma: {new Date(lesson.created_at).toLocaleDateString('tr-TR')}
                    </p>
                  </div>
                  <span style={{ color: 'var(--primary)', fontWeight: 500 }}>Derse Git →</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
