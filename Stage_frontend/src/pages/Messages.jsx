import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { useAutoRefresh } from "../hooks/useAutoRefresh";
import {
    RefreshCw,
    MessageCircle,
    CheckCircle,
    XCircle,
    Send,
} from "lucide-react";

const API_BASE = "http://localhost:8000/api/webhook";

const STATUT_LABELS = {
    nouveau:        { label: "Nouveau",   color: "bg-red-100 text-red-700 border-red-200" },
    lu:             { label: "Lu",        color: "bg-blue-100 text-blue-700 border-blue-200" },
    en_traitement:  { label: "En cours",  color: "bg-orange-100 text-orange-700 border-orange-200" },
    repondu_auto:   { label: "Auto",      color: "bg-purple-100 text-purple-700 border-purple-200" },
    repondu_manuel: { label: "Répondu",   color: "bg-green-100 text-green-700 border-green-200" },
    escalade:       { label: "Escaladé",  color: "bg-red-200 text-red-800 border-red-300" },
    echec:          { label: "Échec",     color: "bg-gray-200 text-gray-700 border-gray-300" },
};

export default function Messages() {
    const [messages, setMessages] = useState([]);
    const [filtre,   setFiltre]   = useState("");
    const [selected, setSelected] = useState(null);
    const [reponse,  setReponse]  = useState("");
    const [envoi,    setEnvoi]    = useState({ loading: false, succes: null });

    const chargerMessages = useCallback(async () => {
        await Promise.resolve();
        try {
            const params = filtre ? { statut: filtre } : {};
            const res = await axios.get(`${API_BASE}/messages/`, { params });
            setMessages(res.data);
        } catch (err) {
            console.error(err);
        }
    }, [filtre]);

    useEffect(() => {
        chargerMessages();
    }, [chargerMessages]);

    // Auto-refresh toutes les 6s — les nouveaux messages arrivent en continu via webhook
    useAutoRefresh(chargerMessages, 6000);

    const handleSelect = async (msg) => {
        setSelected(msg);
        setReponse("");
        setEnvoi({ loading: false, succes: null });

        if (msg.statut === "nouveau") {
            try {
                await axios.post(`${API_BASE}/messages/${msg.id}/marquer-lu/`);
                setSelected((prev) => ({ ...prev, statut: "lu" }));
                setMessages((prev) => prev.map((m) => (m.id === msg.id ? { ...m, statut: "lu" } : m)));
            } catch (err) {
                console.error(err);
            }
        }
    };

    const handleRepondre = async () => {
        if (!reponse.trim()) return;
        setEnvoi({ loading: true, succes: null });
        try {
            await axios.post(`${API_BASE}/messages/${selected.id}/repondre/`, { reponse });
            setEnvoi({ loading: false, succes: true });
            setReponse("");
            await chargerMessages();
            setSelected((prev) => ({ ...prev, statut: "repondu_manuel", reponse_envoyee: reponse }));
        } catch (err) {
            const erreur = err.response?.data?.erreur || "Erreur lors de l'envoi.";
            setEnvoi({ loading: false, succes: false, erreur });
        }
    };

    const handleMarquerRepondu = async () => {
        try {
            await axios.post(`${API_BASE}/messages/${selected.id}/repondre/`, {});
            setSelected((prev) => ({ ...prev, statut: "repondu_manuel" }));
            await chargerMessages();
        } catch (err) {
            console.error(err);
        }
    };

    const peutRepondre = selected && selected.statut !== "repondu_manuel";

    return (
        <div className="flex h-full gap-4 p-6">

            <div className="w-1/2 flex flex-col gap-4">
                <div className="flex items-center justify-between">
                    <h1 className="text-2xl font-bold text-gray-800">Messages reçus</h1>
                    <button onClick={chargerMessages} className="flex items-center gap-1.5 text-sm text-blue-600 hover:underline">
                        <RefreshCw className="w-4 h-4" /> Rafraîchir
                    </button>
                </div>

                <div className="flex gap-2 flex-wrap">
                    <button
                        onClick={() => setFiltre("")}
                        className={`px-3 py-1 rounded-full text-sm border transition ${
                            filtre === "" ? "bg-blue-600 text-white border-blue-600" : "bg-white text-gray-600 border-gray-300 hover:border-blue-400"
                        }`}
                    >
                        Tous
                    </button>
                    {Object.entries(STATUT_LABELS).map(([key, val]) => (
                        <button
                            key={key}
                            onClick={() => setFiltre(key)}
                            className={`px-3 py-1 rounded-full text-sm border transition ${
                                filtre === key ? "bg-blue-600 text-white border-blue-600" : "bg-white text-gray-600 border-gray-300 hover:border-blue-400"
                            }`}
                        >
                            {val.label}
                        </button>
                    ))}
                </div>

                <div className="flex flex-col gap-2 overflow-y-auto">
                    {messages.length === 0 && (
                        <p className="text-gray-400 text-sm text-center mt-8">Aucun message</p>
                    )}
                    {messages.map((msg) => (
                        <div
                            key={msg.id}
                            onClick={() => handleSelect(msg)}
                            className={`cursor-pointer p-4 rounded-xl border transition ${
                                selected?.id === msg.id ? "border-blue-500 bg-blue-50" : "border-gray-200 bg-white hover:border-gray-300"
                            }`}
                        >
                            <div className="flex justify-between items-start">
                                <span className="font-medium text-gray-800">{msg.from_number}</span>
                                <span className={`text-xs px-2 py-0.5 rounded-full font-medium border ${STATUT_LABELS[msg.statut]?.color}`}>
                                    {STATUT_LABELS[msg.statut]?.label}
                                </span>
                            </div>
                            <p className="text-sm text-gray-500 mt-1 truncate">
                                {msg.contenu_texte || "(message vocal)"}
                            </p>
                            <p className="text-xs text-gray-400 mt-1">
                                {new Date(msg.recu_le).toLocaleString("fr-FR")}
                            </p>
                        </div>
                    ))}
                </div>
            </div>

            <div className="w-1/2 bg-white rounded-2xl border border-gray-200 p-6 flex flex-col gap-4 overflow-y-auto">
                {!selected ? (
                    <div className="flex items-center justify-center h-full text-gray-400">
                        Sélectionne un message pour voir le détail
                    </div>
                ) : (
                    <>
                        <h2 className="text-lg font-semibold text-gray-800">Détail du message</h2>

                        <div className="grid grid-cols-2 gap-2 text-sm">
                            <div className="text-gray-500">Numéro</div>
                            <div className="font-medium">{selected.from_number}</div>
                            <div className="text-gray-500">Type</div>
                            <div className="font-medium capitalize">{selected.type_message}</div>
                            <div className="text-gray-500">Reçu le</div>
                            <div className="font-medium">{new Date(selected.recu_le).toLocaleString("fr-FR")}</div>
                            <div className="text-gray-500">Statut</div>
                            <div>
                                <span className={`text-xs px-2 py-0.5 rounded-full font-medium border ${STATUT_LABELS[selected.statut]?.color}`}>
                                    {STATUT_LABELS[selected.statut]?.label}
                                </span>
                            </div>
                        </div>

                        <div>
                            <p className="text-sm text-gray-500 mb-1 font-medium">Message reçu</p>
                            <div className="bg-gray-50 rounded-lg p-3 text-sm text-gray-800 border border-gray-100">
                                {selected.contenu_texte || (
                                    <span className="italic text-gray-400">(message vocal — transcription non disponible)</span>
                                )}
                            </div>
                        </div>

                        {selected.reponse_envoyee && (
                            <div>
                                <p className="text-sm text-gray-500 mb-1 font-medium">Réponse envoyée</p>
                                <div className="bg-green-50 rounded-lg p-3 text-sm text-green-800 border border-green-100">
                                    {selected.reponse_envoyee}
                                </div>
                            </div>
                        )}

                        {peutRepondre && (
                            <div className="flex flex-col gap-3 pt-2 border-t border-gray-100">

                                <a
                                    href={`https://wa.me/${selected.from_number}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="w-full bg-green-500 hover:bg-green-600 text-white py-3 rounded-xl text-sm font-semibold text-center transition flex items-center justify-center gap-2"
                                >
                                    <MessageCircle className="w-4 h-4" /> Ouvrir WhatsApp avec ce client
                                </a>

                                <button
                                    onClick={handleMarquerRepondu}
                                    className="w-full bg-gray-800 hover:bg-gray-900 text-white py-2.5 rounded-lg text-sm font-medium transition flex items-center justify-center gap-2"
                                >
                                    <CheckCircle className="w-4 h-4" /> Marquer comme répondu (déjà répondu dans WhatsApp)
                                </button>

                                <details className="mt-1">
                                    <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700">
                                        Ou envoyer un message texte via l'app
                                    </summary>
                                    <div className="mt-2 flex flex-col gap-2">
                                        <textarea
                                            value={reponse}
                                            onChange={(e) => setReponse(e.target.value)}
                                            placeholder="Écris ta réponse ici..."
                                            rows={3}
                                            className="w-full border border-gray-300 rounded-lg p-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-400"
                                        />
                                        <button
                                            onClick={handleRepondre}
                                            disabled={envoi.loading || !reponse.trim()}
                                            className="w-full bg-blue-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition flex items-center justify-center gap-2"
                                        >
                                            <Send className="w-4 h-4" />
                                            {envoi.loading ? "Envoi en cours..." : "Envoyer via API"}
                                        </button>
                                        {envoi.succes === true && (
                                            <p className="flex items-center justify-center gap-1 text-green-600 text-sm">
                                                <CheckCircle className="w-4 h-4" /> Réponse envoyée !
                                            </p>
                                        )}
                                        {envoi.succes === false && (
                                            <p className="flex items-center justify-center gap-1 text-red-600 text-sm">
                                                <XCircle className="w-4 h-4" /> {envoi.erreur || "Erreur lors de l'envoi"}
                                            </p>
                                        )}
                                    </div>
                                </details>
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    );
}