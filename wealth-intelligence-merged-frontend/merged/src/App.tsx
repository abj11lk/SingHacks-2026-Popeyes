import {
    BrowserRouter,
    Routes,
    Route,
    Navigate,
} from "react-router-dom";

import Layout from "./components/Layout";

import SelectClient from "./pages/SelectClient";
import ClientIntelligence from "./pages/ClientIntelligence";


export default function App() {
    return (
        <BrowserRouter>

            <Layout>

                <Routes>

                    {/* Nothing selected yet -- pick a client from the sidebar */}
                    <Route
                        path="/"
                        element={
                            <SelectClient />
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
