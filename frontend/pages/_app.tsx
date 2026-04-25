import type { AppProps } from 'next/app';
import { AppFooter } from '../components/AppFooter';
import { ToastProvider } from '../components/Toast';

export default function App({ Component, pageProps }: AppProps) {
  return (
    <ToastProvider>
      <Component {...pageProps} />
      <AppFooter />
    </ToastProvider>
  );
}
