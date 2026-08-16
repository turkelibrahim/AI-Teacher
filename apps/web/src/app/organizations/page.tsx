"use client";

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

interface Organization {
  id: string;
  name: string;
  role: string;
}

export default function OrganizationsPage() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const router = useRouter();

  useEffect(() => {
    const fetchUser = async () => {
      const token = localStorage.getItem('access_token');
      if (!token) {
        router.push('/login');
        return;
      }

      try {
        const res = await fetch('http://localhost:8001/api/v1/organizations', {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });

        if (!res.ok) {
          if (res.status === 401) {
            localStorage.removeItem('access_token');
            router.push('/login');
            return;
          }
          throw new Error('Organizasyonlar alınamadı.');
        }

        const data = await res.json();
        const orgs = data.map((org: {id: string; name: string}) => ({
          id: org.id,
          name: org.name,
          role: 'OWNER/MEMBER' // Temporary fallback since roles might not be in this response
        }));
        setOrganizations(orgs);
      } catch (err: unknown) {
        if (err instanceof Error) {
          setError(err.message);
        }
      } finally {
        setLoading(false);
      }
    };

    fetchUser();
  }, [router]);

  const selectOrganization = (orgId: string) => {
    localStorage.setItem('active_org_id', orgId);
    router.push('/lessons');
  };

  return (
    <div style={{
      minHeight: '100vh',
      padding: '2rem',
      background: 'linear-gradient(135deg, #f8fafc 0%, #e0e7ff 100%)'
    }}>
      <div style={{ maxWidth: '800px', margin: '0 auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
          <h2>Organizasyon Seçin</h2>
          <button 
            className="btn btn-secondary"
            onClick={() => {
              localStorage.removeItem('access_token');
              router.push('/login');
            }}
          >
            Çıkış Yap
          </button>
        </div>

        {error && <div style={{ color: 'var(--error)' }}>{error}</div>}
        
        {loading ? (
          <p>Yükleniyor...</p>
        ) : organizations.length === 0 ? (
          <div className="card text-center">
            <p>Herhangi bir organizasyona üye değilsiniz.</p>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1.5rem' }}>
            {organizations.map((org, index) => (
              <div 
                key={org.id} 
                className="card animate-fade-in" 
                style={{ animationDelay: `${index * 0.1}s`, cursor: 'pointer' }}
                onClick={() => selectOrganization(org.id)}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <h3 style={{ fontSize: '1.25rem', marginBottom: '0.5rem' }}>{org.name}</h3>
                  <span style={{ 
                    background: 'var(--primary)', 
                    color: 'white', 
                    fontSize: '0.75rem', 
                    padding: '2px 8px', 
                    borderRadius: '99px' 
                  }}>
                    {org.role}
                  </span>
                </div>
                <p style={{ fontSize: '0.875rem', color: '#64748b' }}>ID: {org.id.split('-')[0]}...</p>
                
                <button className="btn btn-primary" style={{ width: '100%', marginTop: '1.5rem' }}>
                  Giriş Yap
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
