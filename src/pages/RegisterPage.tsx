import { FormEvent, useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import type { RegisterResponse, UserRole } from '@/types';
import { formatDateTime } from '@/utils/format';
import { getErrorMessage } from '@/utils/errors';

const roleOptions: UserRole[] = ['customer', 'factory', 'port', 'warehouse', 'admin'];

function RegisterPage() {
  const navigate = useNavigate();
  const { register, isAuthenticated } = useAuth();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<UserRole>('customer');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<RegisterResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);
    setIsSubmitting(true);

    try {
      const response = await register({
        name,
        email,
        password,
        role,
      });
      setResult(response);
    } catch (error) {
      setErrorMessage(getErrorMessage(error, 'Unable to register account'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-8">
      <section className="panel w-full max-w-xl p-7">
        <p className="text-xs uppercase tracking-[0.22em] text-brand-300">TrustSeal IoT</p>
        <h1 className="mt-2 text-2xl font-semibold text-slate-100">Create monitoring account</h1>
        <p className="mt-2 text-sm text-slate-400">Register to access supply chain telemetry and custody data.</p>

        {errorMessage && (
          <p className="mt-4 rounded-xl border border-status-red/35 bg-status-red/10 px-3 py-2 text-sm text-status-red">
            {errorMessage}
          </p>
        )}

        {result && (
          <div className="mt-4 space-y-3 rounded-xl border border-status-green/35 bg-status-green/10 p-4">
            <p className="text-sm font-medium text-status-green">Registration successful.</p>
            <p className="text-xs text-slate-200">
              Verification token: <span className="font-mono">{result.verification_token}</span>
            </p>
            <p className="text-xs text-slate-300">
              Expires at: {formatDateTime(result.verification_token_expires_at)}
            </p>
            <button
              type="button"
              className="btn-primary"
              onClick={() => navigate('/login', { state: { registeredEmail: email } })}
            >
              Proceed to Login
            </button>
          </div>
        )}

        <form className="mt-6 grid gap-4 md:grid-cols-2" onSubmit={handleSubmit}>
          <div className="space-y-1 md:col-span-2">
            <label htmlFor="name" className="text-sm text-slate-300">
              Name
            </label>
            <input
              id="name"
              name="name"
              type="text"
              className="input-field"
              placeholder="Alex Rivera"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
            />
          </div>

          <div className="space-y-1">
            <label htmlFor="email" className="text-sm text-slate-300">
              Email
            </label>
            <input
              id="email"
              name="email"
              type="email"
              className="input-field"
              placeholder="operator@trustseal.com"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </div>

          <div className="space-y-1">
            <label htmlFor="role" className="text-sm text-slate-300">
              Role
            </label>
            <select
              id="role"
              name="role"
              className="input-field"
              value={role}
              onChange={(event) => setRole(event.target.value as UserRole)}
              required
            >
              {roleOptions.map((option) => (
                <option key={option} value={option}>
                  {option.replace('_', ' ')}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1 md:col-span-2">
            <label htmlFor="password" className="text-sm text-slate-300">
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              className="input-field"
              placeholder="Create a strong password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </div>

          <button type="submit" className="btn-primary md:col-span-2" disabled={isSubmitting}>
            {isSubmitting ? 'Creating account...' : 'Register'}
          </button>
        </form>

        <p className="mt-6 text-sm text-slate-400">
          Already have an account?{' '}
          <Link to="/login" className="font-semibold text-brand-300 transition hover:text-brand-400">
            Login
          </Link>
        </p>
      </section>
    </main>
  );
}

export default RegisterPage;

