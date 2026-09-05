import {
    BrowserRouter,
    Routes,
    Route,
    Navigate,
} from "react-router-dom";

import Layout from "./components/Layout";

import PrioritiesDashboard from "./pages/PrioritiesDashboard";
import ClientIntelligence from "./pages/ClientIntelligence";


export default function App() {
    return (
        <BrowserRouter>

            <Layout>

                <Routes>

                    {/* Book-wide "who calls first" priority dashboard */}
                    <Route
                        path="/"
                        element={
                            <PrioritiesDashboard />
                        }
                    />


                    {/* Client workspace: profile, portfolios, risk panels, AI tabs */}
                    <Route
                        path="/client/:clientId"
                        element={
                            <ClientIntelligence />
                        }
                    />


                    {/* Unknown route */}
                    <Route
                        path="*"
                        element={
                            <Navigate
                                to="/"
                                replace
                            />
                        }
                    />

                </Routes>

            </Layout>

        </BrowserRouter>
    );
}
