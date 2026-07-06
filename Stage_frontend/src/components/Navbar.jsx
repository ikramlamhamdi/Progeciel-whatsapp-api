import { NavLink } from 'react-router-dom'

function Navbar() {
    return (
        <nav className="bg-white shadow-sm border-b border-gray-200">
            <div className="max-w-7xl mx-auto px-4">
                <div className="flex items-center justify-between h-16">

                    {/* Logo */}
                    <div className="flex items-center gap-2">
                        <div className="w-8 h-8 bg-green-500 rounded-lg flex items-center justify-center">
                            <span className="text-white font-bold text-sm">W</span>
                        </div>
                        <span className="font-semibold text-gray-800">WhatsApp Marketing</span>
                    </div>

                    {/* Navigation */}
                    <div className="flex gap-1">
                        {[
                            { to: '/dashboard', label: 'Dashboard' },
                            { to: '/templates', label: 'Templates' },
                            { to: '/clients', label: 'Clients' },
                            { to: '/campagnes', label: 'Campagnes' },
                            { to: "/messages",label: 'Messages'},

                        ].map(({ to, label }) => (
                            <NavLink
                                key={to}
                                to={to}
                                className={({ isActive }) =>
                                    `px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                                        isActive
                                            ? 'bg-green-50 text-green-600'
                                            : 'text-gray-600 hover:bg-gray-100'
                                    }`
                                }
                            >
                                {label}
                            </NavLink>
                        ))}
                    </div>

                </div>
            </div>
        </nav>
    )
}

export default Navbar