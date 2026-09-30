import { QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router'

import { Layout } from './components/Layout'
import { EmptyState } from './components/ui'
import { makeQueryClient } from './lib/queryClient'
import { OverviewPage } from './pages/OverviewPage'
import { ReleasesPage } from './pages/ReleasesPage'
import { RepliesPage } from './pages/RepliesPage'
import { ReviewsPage } from './pages/ReviewsPage'
import { ThemesPage } from './pages/ThemesPage'

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<OverviewPage />} />
        <Route path="themes" element={<ThemesPage />} />
        <Route path="releases" element={<ReleasesPage />} />
        <Route path="reviews" element={<ReviewsPage />} />
        <Route path="replies" element={<RepliesPage />} />
        <Route path="*" element={<EmptyState title="Page not found" />} />
      </Route>
    </Routes>
  )
}

export function App() {
  const [client] = useState(makeQueryClient)
  return (
    <QueryClientProvider client={client}>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </QueryClientProvider>
  )
}
