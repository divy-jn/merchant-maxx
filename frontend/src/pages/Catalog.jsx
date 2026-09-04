import { useState, useEffect } from 'react';
import { API_BASE_URL } from '../config';
import { useAuth } from '../context/AuthContext';
import './Catalog.css';

export default function Catalog() {
  const { token } = useAuth();
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    fetch(`${API_BASE_URL}/catalog/`, { headers })
      .then(res => {
        if (!res.ok) throw new Error('Failed to fetch catalog');
        return res.json();
      })
      .then(data => {
        setProducts(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) return <div className="loading animate-fade-in">Loading catalog...</div>;
  if (error) return <div className="error animate-fade-in">{error}</div>;

  return (
    <div className="animate-fade-in">
      <div className="catalog-header">
        <h1>Product Catalog</h1>
        <p>Live inventory synced with Razorpay.</p>
      </div>

      <div className="catalog-grid">
        {products.map(product => (
          <div key={product.id} className="product-card glass-panel">
            <div className="product-header">
              <h3 className="product-title">{product.name}</h3>
              <span className="product-price">
                {product.currency === 'INR' ? '₹' : product.currency} 
                {(product.amount / 100).toLocaleString()}
              </span>
            </div>
            <p className="product-desc">{product.description}</p>
            <div className="product-footer">
              <span className={`product-status ${product.active !== false ? 'in-stock' : 'out-of-stock'}`}>
                {product.active !== false ? '● In Stock' : '○ Out of Stock'}
              </span>
              <button className="btn btn-outline" style={{ padding: '0.25rem 0.75rem', fontSize: '0.875rem' }}>
                View
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
