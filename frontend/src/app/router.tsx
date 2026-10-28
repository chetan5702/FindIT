import { createBrowserRouter } from 'react-router-dom'
import { GuestRoute, ProtectedRoute } from './auth'
import { AuthLayout, AppLayout, DynamicAppLayout, PublicLayout } from '../components/layouts'
import { LandingPage } from '../pages/marketing'
import { IdentityPage } from '../pages/identity'
import { LoginPage, RegisterPage } from '../pages/auth'
import { BrowseReportsPage, ReportFormPage } from '../pages/reports'
import { ClaimFormPage, MatchesPage, ReportDetailPage } from '../pages/report-detail'
import { ClaimDetailPage, MyActivityPage } from '../pages/activity'
import { NotificationsPage, ProfilePage } from '../pages/account'
import { CustodyPage, HandoversPage, StaffClaimDetailPage, StaffClaimsPage, StaffDashboardPage } from '../pages/staff'
import { AdminDashboardPage, AuditPage, CategoriesPage, LocationQrPage, LocationsPage, UsersPage } from '../pages/admin'
import { NotFoundPage, RoleHomePage, RouteErrorPage } from '../pages/system'

export const router = createBrowserRouter([
  { element: <AuthLayout />, children: [
    { path: 'verify-email', element: <IdentityPage mode="verify" /> },
    { path: 'forgot-password', element: <IdentityPage mode="forgot" /> },
    { path: 'reset-password', element: <IdentityPage mode="reset" /> },
  ] },
  {
    element: <PublicLayout />,
    errorElement: <RouteErrorPage />,
    children: [
      { index: true, element: <LandingPage /> },
      { path: 'browse', element: <div className="page-wrap py-10"><BrowseReportsPage publicMode /></div> },
    ],
  },
  {
    element: <GuestRoute />,
    children: [{
      element: <AuthLayout />,
      children: [
        { path: 'login', element: <LoginPage /> },
        { path: 'register', element: <RegisterPage /> },
      ],
    }],
  },
  {
    element: <ProtectedRoute />,
    children: [{
      path: 'app',
      element: <DynamicAppLayout />,
      children: [
        { index: true, element: <RoleHomePage /> },
        { path: 'browse', element: <BrowseReportsPage /> },
        { path: 'reports/:id', element: <ReportDetailPage /> },
        { path: 'notifications', element: <NotificationsPage /> },
        { path: 'profile', element: <ProfilePage /> },
        {
          element: <ProtectedRoute roles={['student']} />,
          children: [
            { path: 'report/lost', element: <ReportFormPage type="lost" /> },
            { path: 'report/found', element: <ReportFormPage type="found" /> },
            { path: 'reports/:id/edit', element: <ReportFormPage /> },
            { path: 'reports/:id/matches', element: <MatchesPage /> },
            { path: 'reports/:id/claim', element: <ClaimFormPage /> },
            { path: 'claims/:id', element: <ClaimDetailPage /> },
            { path: 'activity', element: <MyActivityPage /> },
          ],
        },
      ],
    }],
  },
  {
    element: <ProtectedRoute roles={['staff', 'admin']} />,
    children: [{
      path: 'staff',
      element: <AppLayout kind="staff" />,
      children: [
        { index: true, element: <StaffDashboardPage /> },
        { path: 'custody', element: <CustodyPage /> },
        { path: 'claims', element: <StaffClaimsPage /> },
        { path: 'claims/:id', element: <StaffClaimDetailPage /> },
        { path: 'handovers', element: <HandoversPage /> },
      ],
    }],
  },
  {
    element: <ProtectedRoute roles={['admin']} />,
    children: [{
      path: 'admin',
      element: <AppLayout kind="admin" />,
      children: [
        { index: true, element: <AdminDashboardPage /> },
        { path: 'categories', element: <CategoriesPage /> },
        { path: 'locations', element: <LocationsPage /> },
        { path: 'locations/:id/qr', element: <LocationQrPage /> },
        { path: 'users', element: <UsersPage /> },
        { path: 'audit', element: <AuditPage /> },
      ],
    }],
  },
  { path: '*', element: <NotFoundPage /> },
])
