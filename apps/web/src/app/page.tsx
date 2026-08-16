import Link from 'next/link';

export default function Home() {
  return (
    <main style={{ 
      minHeight: '100vh', 
      display: 'flex', 
      flexDirection: 'column',
      alignItems: 'center', 
      justifyContent: 'center',
      padding: '2rem',
      textAlign: 'center',
      background: 'radial-gradient(circle at 50% -20%, #e0e7ff, transparent 80%)'
    }}>
      <div className="glass animate-fade-in" style={{
        padding: '3rem',
        borderRadius: '1.5rem',
        maxWidth: '600px',
        width: '100%'
      }}>
        <div style={{ marginBottom: '2rem' }}>
          <span style={{ 
            background: 'var(--primary)', 
            color: 'white', 
            padding: '4px 12px', 
            borderRadius: '99px',
            fontSize: '0.875rem',
            fontWeight: 600,
            display: 'inline-block',
            marginBottom: '1rem'
          }}>
            Platform v2.0
          </span>
          <h1>Canlı Öğretmen AI</h1>
          <p style={{ fontSize: '1.125rem', marginTop: '1rem' }}>
            Akıllı doküman analizi ve RAG destekli yapay zeka ile kişiselleştirilmiş eğitim deneyimi.
          </p>
        </div>
        
        <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
          <Link href="/login" className="btn btn-primary" style={{ padding: '1rem 2rem', fontSize: '1rem' }}>
            Sisteme Giriş Yap
          </Link>
          <a href="http://localhost:8001/docs" target="_blank" rel="noopener noreferrer" className="btn btn-secondary" style={{ padding: '1rem 2rem', fontSize: '1rem' }}>
            API Dokümanları
          </a>
        </div>
      </div>
    </main>
  );
}
