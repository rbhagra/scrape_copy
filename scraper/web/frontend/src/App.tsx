import { Routes, Route, Link, useLocation } from 'react-router-dom';
import BillsBrowser from './components/BillsBrowser';
import ScrapeForm from './components/ScrapeForm';
import JobStatus from './components/JobStatus';

function App() {
  const location = useLocation();
  
  return (
    <div className="min-h-screen">
      <nav className="sticky top-0 z-50 bg-white shadow-md shadow-blue-200 border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex">
              <div className="flex-shrink-0 flex items-center">
                <h1>
                  <Link to="/" className="text-xl font-bold text-blue-900">
                    Bill Viewer
                  </Link>
                </h1>
              </div>
              <div className="hidden sm:ml-6 sm:flex sm:space-x-8">
                <Link
                  to="/"
                  className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                    location.pathname === '/'
                      ? 'border-blue-500 text-gray-900'
                      : 'border-transparent text-gray-500 hover:bg-blue-50 hover:border-gray-300 hover:text-gray-700'
                  }`}
                >
                  Browse Bills
                </Link>
                <Link
                  to="/scrape"
                  className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                    location.pathname.startsWith('/scrape')
                      ? 'border-blue-500 text-gray-900'
                      : 'border-transparent text-gray-500 hover:bg-blue-50 hover:border-gray-300 hover:text-gray-700'
                  }`}
                >
                  New Scrape
                </Link>
              </div>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <Routes>
          <Route path="/" element={<BillsBrowser />} />
          <Route path="/scrape" element={<ScrapeForm />} />
          <Route path="/scrape/:jobId" element={<JobStatus />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
