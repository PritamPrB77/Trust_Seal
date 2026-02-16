import { FormEvent, useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { getErrorMessage } from '@/utils/errors';

function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, isAuthenticated } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fromPath = (location.state as { from?: string } | null)?.from ?? '/dashboard';
  const registeredEmail = (location.state as { registeredEmail?: string } | null)?.registeredEmail ?? '';

  if (isAuthenticated) {
    return <Navigate to={fromPath} replace />;
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);
    setIsSubmitting(true);

    try {
      await login(email, password);
      navigate(fromPath, { replace: true });
    } catch (error) {
      setErrorMessage(getErrorMessage(error, 'Unable to login'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-8">
      <section className="panel w-full max-w-md p-7">
        <p className="text-xs uppercase tracking-[0.22em] text-brand-300">TrustSeal IoT</p>
        <h1 className="mt-2 text-2xl font-semibold text-slate-100">Sign in to monitor shipments</h1>
        <p className="mt-2 text-sm text-slate-400">JWT authenticated access to your IoT monitoring dashboard.</p>

        {registeredEmail && (
          <p className="mt-4 rounded-xl border border-status-green/35 bg-status-green/10 px-3 py-2 text-sm text-status-green">
            Registration completed for {registeredEmail}. You can sign in now.
          </p>
        )}

        {errorMessage && (
          <p className="mt-4 rounded-xl border border-status-red/35 bg-status-red/10 px-3 py-2 text-sm text-status-red">
            {errorMessage}
          </p>
        )}

        <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
          <div className="space-y-1">
            <label htmlFor="email" className="text-sm text-slate-300">
              Email
            </label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              className="input-field"
              placeholder="operator@trustseal.com"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </div>

          <div className="space-y-1">
            <label htmlFor="password" className="text-sm text-slate-300">
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              className="input-field"
              placeholder="********"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </div>

          <button type="submit" className="btn-primary w-full" disabled={isSubmitting}>
            {isSubmitting ? 'Signing in...' : 'Login'}
          </button>
        </form>

        <p className="mt-6 text-sm text-slate-400">
          New account?{' '}
          <Link to="/register" className="font-semibold text-brand-300 transition hover:text-brand-400">
            Register here
          </Link>
        </p>
      </section>
    </main>
  );
}

export default LoginPage;
