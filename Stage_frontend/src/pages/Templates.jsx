import { useEffect, useState, useMemo } from 'react'
import api from '../api/axios'
import {
    RefreshCw,
    Plus,
    X,
    Trash2,
    Image as ImageIcon,
    Video,
    FileText,
    Type,
    MessageSquare,
    CheckCircle,
    AlertCircle,
    Clock,
    Globe,
    Hash,
    Inbox,
    Search,
    SlidersHorizontal,
} from 'lucide-react'

const TYPES_HEADER_MEDIA = ['IMAGE', 'VIDEO', 'DOCUMENT']

const FORM_INITIAL = {
    nom: '',
    categorie: 'MARKETING',
    langue: 'fr',
    type_header: 'NONE',
    contenu_header: '',
    header_handle: '',
    contenu_body: '',
    contenu_footer: '',
    exemples_variables: '',
    boutons: [],
}

const BOUTON_VIDE = {
    type_bouton: 'QUICK_REPLY',
    texte: '',
    url: '',
    numero_telephone: '',
}

const FILTRES_INITIAL = {
    recherche: '',
    statut: 'tous',
    categorie: 'tous',
    langue: 'tous',
    masquerExemplesMeta: false,
}

function messageErreurApi(err, fallback) {
    const data = err.response?.data || {}
    return [
        data.erreur || fallback,
        data.detail,
        data.code ? `code: ${data.code}` : null,
        data.fbtrace_id ? `fbtrace_id: ${data.fbtrace_id}` : null,
    ].filter(Boolean).join(' | ')
}

const couleurStatut = (statut) => {
    const couleurs = {
        approuve: 'bg-green-100 text-green-700 border-green-200',
        en_attente: 'bg-yellow-100 text-yellow-700 border-yellow-200',
        rejete: 'bg-red-100 text-red-700 border-red-200',
        suspendu: 'bg-gray-100 text-gray-700 border-gray-200',
    }
    return couleurs[statut] || 'bg-gray-100 text-gray-700'
}

const iconeStatut = (statut) => {
    const icones = {
        approuve: <CheckCircle className="w-4 h-4" />,
        en_attente: <Clock className="w-4 h-4" />,
        rejete: <AlertCircle className="w-4 h-4" />,
        suspendu: <AlertCircle className="w-4 h-4" />,
    }
    return icones[statut] || null
}

const couleurCategorie = (categorie) => {
    const couleurs = {
        MARKETING: 'bg-blue-50 text-blue-700 border-blue-200',
        UTILITY: 'bg-purple-50 text-purple-700 border-purple-200',
        AUTHENTICATION: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    }
    return couleurs[categorie] || 'bg-gray-50 text-gray-700 border-gray-200'
}

const iconeHeader = (type) => {
    const icones = {
        IMAGE: <ImageIcon className="w-4 h-4" />,
        VIDEO: <Video className="w-4 h-4" />,
        DOCUMENT: <FileText className="w-4 h-4" />,
        TEXT: <Type className="w-4 h-4" />,
    }
    return icones[type] || null
}

// Heuristique : les templates d'exemple Meta (comptes de test) sont préfixés "jaspers_market_"
const estExempleMeta = (nom) => nom?.toLowerCase().startsWith('jaspers_market')

// ── Barre de filtres ──────────────────────────────────────────
function BarreFiltres({ filtres, onChange, statutsDisponibles, categoriesDisponibles, languesDisponibles, nbResultats, nbTotal }) {
    const majFiltre = (champ, valeur) => onChange({ ...filtres, [champ]: valeur })

    const filtresActifs =
        filtres.recherche !== '' ||
        filtres.statut !== 'tous' ||
        filtres.categorie !== 'tous' ||
        filtres.langue !== 'tous' ||
        filtres.masquerExemplesMeta

    return (
        <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6 shadow-sm">
            <div className="flex flex-col md:flex-row gap-3">
                {/* Recherche */}
                <div className="relative flex-1">
                    <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
                    <input
                        value={filtres.recherche}
                        onChange={(e) => majFiltre('recherche', e.target.value)}
                        placeholder="Rechercher un template..."
                        className="w-full border border-gray-200 rounded-lg pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                    />
                </div>

                {/* Statut */}
                <select
                    value={filtres.statut}
                    onChange={(e) => majFiltre('statut', e.target.value)}
                    className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                >
                    <option value="tous">Tous les statuts</option>
                    {statutsDisponibles.map((s) => (
                        <option key={s} value={s}>{s}</option>
                    ))}
                </select>

                {/* Catégorie */}
                <select
                    value={filtres.categorie}
                    onChange={(e) => majFiltre('categorie', e.target.value)}
                    className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                >
                    <option value="tous">Toutes catégories</option>
                    {categoriesDisponibles.map((c) => (
                        <option key={c} value={c}>{c}</option>
                    ))}
                </select>

                {/* Langue */}
                <select
                    value={filtres.langue}
                    onChange={(e) => majFiltre('langue', e.target.value)}
                    className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                >
                    <option value="tous">Toutes langues</option>
                    {languesDisponibles.map((l) => (
                        <option key={l} value={l}>{l}</option>
                    ))}
                </select>
            </div>

            <div className="flex items-center justify-between mt-3">
                <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
                    <input
                        type="checkbox"
                        checked={filtres.masquerExemplesMeta}
                        onChange={(e) => majFiltre('masquerExemplesMeta', e.target.checked)}
                        className="rounded border-gray-300 text-green-600 focus:ring-green-400"
                    />
                    Masquer les exemples Meta (jaspers_market_*)
                </label>

                <div className="flex items-center gap-3">
                    <span className="text-xs text-gray-400">
                        {nbResultats} / {nbTotal} template{nbTotal !== 1 ? 's' : ''}
                    </span>
                    {filtresActifs && (
                        <button
                            onClick={() => onChange(FILTRES_INITIAL)}
                            className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 underline"
                        >
                            <SlidersHorizontal className="w-3.5 h-3.5" /> Réinitialiser
                        </button>
                    )}
                </div>
            </div>
        </div>
    )
}

// ── Carte template ──────────────────────────────────────────
function CarteTemplate({ template, onOuvrir, onSupprimer }) {
    return (
        <div
            onClick={() => onOuvrir(template)}
            className="group relative bg-white rounded-xl border border-gray-200 p-5 shadow-sm hover:shadow-lg hover:border-green-300 transition-all cursor-pointer overflow-hidden"
        >
            <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-green-400 to-emerald-400 opacity-0 group-hover:opacity-100 transition-opacity" />

            <button
                onClick={(e) => { e.stopPropagation(); onSupprimer(template.id) }}
                className="absolute top-4 right-4 p-2 rounded-lg text-gray-300 hover:text-red-600 hover:bg-red-50 opacity-0 group-hover:opacity-100 transition-all z-10"
                title="Supprimer"
            >
                <Trash2 className="w-5 h-5" />
            </button>

            <div className="pr-10 mb-3">
                <div className="flex items-center gap-2 mb-2">
                    <h2 className="font-semibold text-gray-800 truncate">{template.nom}</h2>
                    {estExempleMeta(template.nom) && (
                        <span className="shrink-0 text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 font-medium">
                            exemple Meta
                        </span>
                    )}
                </div>
                <div className="flex flex-wrap gap-2">
                    <span className={`inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full border font-medium ${couleurStatut(template.statut)}`}>
                        {iconeStatut(template.statut)}
                        {template.statut}
                    </span>
                    <span className={`text-xs px-2 py-1 rounded-full border font-medium ${couleurCategorie(template.categorie)}`}>
                        {template.categorie}
                    </span>
                </div>
            </div>

            <div className="bg-gradient-to-b from-emerald-50 to-emerald-50/50 border border-emerald-100 rounded-lg p-4 mb-4">
                {template.type_header && template.type_header !== 'NONE' && (
                    <div className="flex items-center gap-2 text-xs font-semibold text-emerald-700 mb-2 pb-2 border-b border-emerald-200">
                        {iconeHeader(template.type_header)}
                        <span>{template.type_header === 'TEXT' ? template.contenu_header : template.type_header}</span>
                    </div>
                )}
                <p className="text-sm text-gray-700 line-clamp-3 leading-relaxed">
                    {template.contenu_body || <span className="italic text-gray-300">Pas de contenu</span>}
                </p>
                {template.contenu_footer && (
                    <p className="text-xs text-gray-500 mt-3 pt-3 border-t border-emerald-100 truncate">
                        {template.contenu_footer}
                    </p>
                )}
            </div>

            <div className="flex items-center justify-between text-xs text-gray-500">
                <span className="flex items-center gap-1">
                    <Globe className="w-3.5 h-3.5" /> {template.langue}
                </span>
                <span className="flex items-center gap-1">
                    <Hash className="w-3.5 h-3.5" /> {template.nombre_variables} variable{template.nombre_variables !== 1 ? 's' : ''}
                </span>
                {template.boutons?.length > 0 && (
                    <span className="flex items-center gap-1 text-gray-600 font-medium">
                        <MessageSquare className="w-3.5 h-3.5" />
                        {template.boutons.length}
                    </span>
                )}
            </div>
        </div>
    )
}

// ── Panneau détail ──────────────────────────────────────────
function DetailTemplate({ template, onClose, onSupprimer }) {
    const handleSupprimer = async () => {
        const succes = await onSupprimer(template.id)
        if (succes) onClose()
    }

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
            <div
                className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="flex items-start justify-between mb-5 pb-4 border-b border-gray-200">
                    <div>
                        <h2 className="text-2xl font-bold text-gray-800 mb-3">{template.nom}</h2>
                        <div className="flex gap-2 flex-wrap">
                            <span className={`inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded-full border font-medium ${couleurStatut(template.statut)}`}>
                                {iconeStatut(template.statut)}
                                {template.statut}
                            </span>
                            <span className={`text-xs px-3 py-1.5 rounded-full border font-medium ${couleurCategorie(template.categorie)}`}>
                                {template.categorie}
                            </span>
                            <span className="text-xs px-3 py-1.5 rounded-full bg-gray-100 text-gray-700 border border-gray-200 font-medium">
                                {template.langue}
                            </span>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="text-gray-400 hover:text-gray-600 p-2 rounded-lg hover:bg-gray-100 transition-colors"
                    >
                        <X className="w-6 h-6" />
                    </button>
                </div>

                <div className="grid grid-cols-3 gap-3 mb-6">
                    <div className="bg-blue-50 rounded-lg p-4 border border-blue-100 text-center">
                        <div className="flex justify-center mb-2">
                            <MessageSquare className="w-5 h-5 text-blue-600" />
                        </div>
                        <p className="text-xs text-gray-600 mb-1">Boutons</p>
                        <p className="text-2xl font-bold text-blue-700">{template.boutons?.length || 0}</p>
                    </div>
                    <div className="bg-purple-50 rounded-lg p-4 border border-purple-100 text-center">
                        <div className="flex justify-center mb-2">
                            <Hash className="w-5 h-5 text-purple-600" />
                        </div>
                        <p className="text-xs text-gray-600 mb-1">Variables</p>
                        <p className="text-2xl font-bold text-purple-700">{template.nombre_variables}</p>
                    </div>
                    <div className="bg-emerald-50 rounded-lg p-4 border border-emerald-100 text-center">
                        <div className="flex justify-center mb-2">
                            {iconeHeader(template.type_header) || <FileText className="w-5 h-5 text-emerald-600" />}
                        </div>
                        <p className="text-xs text-gray-600 mb-1">Header</p>
                        <p className="text-lg font-bold text-emerald-700">{template.type_header || 'NONE'}</p>
                    </div>
                </div>

                <div className="flex flex-col gap-4">
                    {template.contenu_header && (
                        <div>
                            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Header</p>
                            <div className="bg-emerald-50 rounded-lg px-4 py-3 text-sm text-gray-800 border border-emerald-100 font-medium">
                                {template.contenu_header}
                            </div>
                        </div>
                    )}

                    <div>
                        <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Body</p>
                        <div className="bg-gray-50 rounded-lg px-4 py-3 text-sm text-gray-700 border border-gray-200 whitespace-pre-line leading-relaxed">
                            {template.contenu_body || <span className="italic text-gray-300">—</span>}
                        </div>
                    </div>

                    {template.contenu_footer && (
                        <div>
                            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Footer</p>
                            <div className="bg-gray-50 rounded-lg px-4 py-3 text-sm text-gray-600 border border-gray-200 italic">
                                {template.contenu_footer}
                            </div>
                        </div>
                    )}

                    {template.exemples_variables_body?.length > 0 && (
                        <div>
                            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Exemples de variables</p>
                            <div className="flex gap-2 flex-wrap">
                                {template.exemples_variables_body.map((ex, i) => (
                                    <span key={i} className="text-xs bg-purple-50 text-purple-700 px-3 py-1.5 rounded-full border border-purple-200 font-medium">
                                        {`{{${i + 1}}}`} = {ex}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}

                    {template.boutons?.length > 0 && (
                        <div>
                            <p className="text-xs font-semibold text-gray-500 uppercase mb-3">Boutons ({template.boutons.length})</p>
                            <div className="flex flex-col gap-2">
                                {template.boutons.map((b) => (
                                    <div key={b.id} className="flex items-center gap-3 bg-gradient-to-r from-green-50 to-emerald-50 rounded-lg px-4 py-3 border border-green-200 text-sm">
                                        <span className="text-xs bg-green-200 text-green-800 px-2.5 py-1 rounded-full font-semibold">{b.type_bouton}</span>
                                        <span className="font-semibold text-gray-800 flex-1">{b.texte}</span>
                                        {b.url && <span className="text-gray-500 text-xs max-w-[200px] truncate">{b.url}</span>}
                                        {b.numero_telephone && <span className="text-gray-500 text-xs">{b.numero_telephone}</span>}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    <div className="grid grid-cols-2 gap-3 pt-4 border-t border-gray-200 text-xs text-gray-500">
                        <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
                            <p className="font-medium mb-1">Créé le</p>
                            <p className="text-gray-700 font-semibold">
                                {template.date_creation_meta
                                    ? new Date(template.date_creation_meta).toLocaleDateString('fr-FR')
                                    : '—'}
                            </p>
                        </div>
                        <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
                            <p className="font-medium mb-1">Approuvé le</p>
                            <p className="text-gray-700 font-semibold">
                                {template.date_approbation
                                    ? new Date(template.date_approbation).toLocaleDateString('fr-FR')
                                    : '—'}
                            </p>
                        </div>
                    </div>

                    <div className="pt-4 border-t border-gray-200 flex justify-between gap-3">
                        <button
                            onClick={onClose}
                            className="flex-1 px-4 py-2.5 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 transition-colors"
                        >
                            Fermer
                        </button>
                        <button
                            onClick={handleSupprimer}
                            className="flex items-center gap-2 px-4 py-2.5 bg-red-50 text-red-600 rounded-lg text-sm font-medium hover:bg-red-100 border border-red-200 transition-colors"
                        >
                            <Trash2 className="w-4 h-4" /> Supprimer
                        </button>
                    </div>
                </div>
            </div>
        </div>
    )
}

// ── Page principale ─────────────────────────────────────────
function Templates() {
    const [templates, setTemplates] = useState([])
    const [loading, setLoading] = useState(true)
    const [showForm, setShowForm] = useState(false)
    const [formLoading, setFormLoading] = useState(false)
    const [uploadLoading, setUploadLoading] = useState(false)
    const [message, setMessage] = useState(null)
    const [headerFile, setHeaderFile] = useState(null)
    const [form, setForm] = useState(FORM_INITIAL)
    const [templateDetail, setTemplateDetail] = useState(null)
    const [filtres, setFiltres] = useState(FILTRES_INITIAL)

    const headerEstMedia = TYPES_HEADER_MEDIA.includes(form.type_header)

    const chargerTemplates = async () => {
        setLoading(true)
        try {
            const res = await api.get('/templates/')
            setTemplates(res.data)
        } catch (err) {
            setMessage({ type: 'error', text: messageErreurApi(err, 'Erreur lors du chargement des templates.') })
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        const fetchInitialTemplates = async () => {
            await Promise.resolve()
            setLoading(true)
            try {
                const res = await api.get('/templates/')
                setTemplates(res.data)
            } catch (err) {
                setMessage({ type: 'error', text: messageErreurApi(err, 'Erreur lors du chargement des templates.') })
            } finally {
                setLoading(false)
            }
        }
        fetchInitialTemplates()
    }, [])

    const synchroniser = async () => {
        setLoading(true)
        setMessage(null)
        try {
            await api.post('/templates/synchroniser/')
            await chargerTemplates()
            setMessage({ type: 'success', text: 'Templates synchronisés avec succès !' })
        } catch (err) {
            setMessage({ type: 'error', text: messageErreurApi(err, 'Erreur lors de la synchronisation.') })
        } finally {
            setLoading(false)
        }
    }

    const handleChange = (e) => {
        const { name, value } = e.target
        setForm((prev) => ({
            ...prev,
            [name]: value,
            ...(name === 'type_header' && value !== 'TEXT' ? { contenu_header: '' } : {}),
            ...(name === 'type_header' && !TYPES_HEADER_MEDIA.includes(value) ? { header_handle: '' } : {}),
        }))
        if (name === 'type_header') setHeaderFile(null)
    }

    const uploadHeaderMedia = async () => {
        if (!headerFile) {
            setMessage({ type: 'error', text: 'Choisissez un fichier header avant l\'upload.' })
            return
        }
        setUploadLoading(true)
        setMessage(null)
        try {
            const data = new FormData()
            data.append('fichier', headerFile)
            data.append('type_header', form.type_header)
            const res = await api.post('/templates/upload-header-media/', data, {
                headers: { 'Content-Type': 'multipart/form-data' },
            })
            setForm((prev) => ({
                ...prev,
                type_header: res.data.type_header || prev.type_header,
                header_handle: res.data.header_handle,
            }))
            setMessage({ type: 'success', text: 'Média uploadé chez Meta avec succès.' })
        } catch (err) {
            setMessage({ type: 'error', text: messageErreurApi(err, 'Erreur lors de l\'upload du média.') })
        } finally {
            setUploadLoading(false)
        }
    }

    const handleBoutonChange = (index, field, value) => {
        const boutons = [...form.boutons]
        boutons[index] = { ...boutons[index], [field]: value }
        setForm({ ...form, boutons })
    }

    const ajouterBouton = () => {
        if (form.boutons.length >= 3) return
        setForm({ ...form, boutons: [...form.boutons, { ...BOUTON_VIDE }] })
    }

    const supprimerBouton = (index) => {
        setForm({ ...form, boutons: form.boutons.filter((_, i) => i !== index) })
    }

    const resetForm = () => {
        setForm(FORM_INITIAL)
        setHeaderFile(null)
    }

    const normaliserBoutons = () => {
        return form.boutons
            .filter((b) => b.texte.trim())
            .map((b, index) => ({
                ordre: index + 1,
                type_bouton: b.type_bouton,
                texte: b.texte.trim(),
                url: b.type_bouton === 'URL' ? b.url.trim() : '',
                numero_telephone: b.type_bouton === 'PHONE_NUMBER' ? b.numero_telephone.trim() : '',
            }))
    }

    const handleSubmit = async (e) => {
        e.preventDefault()
        setFormLoading(true)
        setMessage(null)
        if (headerEstMedia && !form.header_handle) {
            setMessage({ type: 'error', text: 'Uploadez d\'abord le média header pour obtenir le header_handle Meta.' })
            setFormLoading(false)
            return
        }
        try {
            const payload = {
                nom: form.nom,
                categorie: form.categorie,
                langue: form.langue,
                type_header: form.type_header,
                contenu_header: form.type_header === 'TEXT' ? form.contenu_header : '',
                header_handle: headerEstMedia ? form.header_handle : '',
                contenu_body: form.contenu_body,
                contenu_footer: form.contenu_footer,
                exemples_variables: form.exemples_variables
                    ? form.exemples_variables.split(',').map((v) => v.trim()).filter(Boolean)
                    : [],
                boutons: normaliserBoutons(),
            }
            await api.post('/templates/creer/', payload)
            setMessage({ type: 'success', text: 'Template soumis à Meta avec succès !' })
            setShowForm(false)
            resetForm()
            await chargerTemplates()
        } catch (err) {
            setMessage({ type: 'error', text: messageErreurApi(err, 'Erreur lors de la création.') })
        } finally {
            setFormLoading(false)
        }
    }

    const supprimerTemplate = async (id) => {
        if (!window.confirm('Supprimer ce template chez Meta et en base ?')) return false
        try {
            await api.delete(`/templates/${id}/supprimer/`)
            setMessage({ type: 'success', text: 'Template supprimé avec succès.' })
            await chargerTemplates()
            return true
        } catch (err) {
            setMessage({ type: 'error', text: messageErreurApi(err, 'Erreur lors de la suppression.') })
            return false
        }
    }

    // Valeurs disponibles pour les selects, dérivées des templates réellement présents
    const statutsDisponibles = useMemo(
        () => [...new Set(templates.map((t) => t.statut))].sort(),
        [templates]
    )
    const categoriesDisponibles = useMemo(
        () => [...new Set(templates.map((t) => t.categorie))].sort(),
        [templates]
    )
    const languesDisponibles = useMemo(
        () => [...new Set(templates.map((t) => t.langue))].sort(),
        [templates]
    )

    const templatesFiltres = useMemo(() => {
        const recherche = filtres.recherche.trim().toLowerCase()
        return templates.filter((t) => {
            if (recherche && !t.nom.toLowerCase().includes(recherche) && !t.contenu_body?.toLowerCase().includes(recherche)) {
                return false
            }
            if (filtres.statut !== 'tous' && t.statut !== filtres.statut) return false
            if (filtres.categorie !== 'tous' && t.categorie !== filtres.categorie) return false
            if (filtres.langue !== 'tous' && t.langue !== filtres.langue) return false
            if (filtres.masquerExemplesMeta && estExempleMeta(t.nom)) return false
            return true
        })
    }, [templates, filtres])

    return (
        <div>
            {templateDetail && (
                <DetailTemplate
                    template={templateDetail}
                    onClose={() => setTemplateDetail(null)}
                    onSupprimer={supprimerTemplate}
                />
            )}

            <div className="flex flex-col gap-4 mb-6">
                <div>
                    <h1 className="text-3xl font-bold text-gray-900">Templates WhatsApp</h1>
                    <p className="text-gray-500 text-sm mt-1">Gérez vos templates approuvés par Meta</p>
                </div>
                <div className="flex gap-2 flex-wrap">
                    <button
                        onClick={synchroniser}
                        disabled={loading}
                        className="flex items-center gap-2 px-4 py-2.5 bg-white border border-gray-300 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors disabled:opacity-50"
                    >
                        <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Synchroniser
                    </button>
                    <button
                        onClick={() => setShowForm(!showForm)}
                        className="flex items-center gap-2 px-4 py-2.5 bg-green-500 text-white rounded-lg text-sm font-medium hover:bg-green-600 transition-colors shadow-md hover:shadow-lg"
                    >
                        {showForm ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
                        {showForm ? 'Annuler' : 'Nouveau template'}
                    </button>
                </div>
            </div>

            {message && (
                <div className={`mb-4 px-4 py-3 rounded-lg text-sm font-medium ${
                    message.type === 'success'
                        ? 'bg-green-50 text-green-700 border border-green-200'
                        : 'bg-red-50 text-red-700 border border-red-200'
                }`}>
                    {message.text}
                    <button onClick={() => setMessage(null)} className="ml-3 text-xs underline">Fermer</button>
                </div>
            )}

            {showForm && (
                <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6 shadow-sm">
                    <h2 className="text-lg font-semibold text-gray-800 mb-4">Nouveau template</h2>
                    <form onSubmit={handleSubmit} className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Nom</label>
                            <input name="nom" value={form.nom} onChange={handleChange} placeholder="ex: promo_ete" required
                                   className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400" />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Catégorie</label>
                            <select name="categorie" value={form.categorie} onChange={handleChange}
                                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400">
                                <option value="MARKETING">MARKETING</option>
                                <option value="UTILITY">UTILITY</option>
                                <option value="AUTHENTICATION">AUTHENTICATION</option>
                            </select>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Langue</label>
                            <input name="langue" value={form.langue} onChange={handleChange} placeholder="ex: fr, en_US, ar"
                                   className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400" />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Type de header</label>
                            <select name="type_header" value={form.type_header} onChange={handleChange}
                                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400">
                                <option value="NONE">Aucun</option>
                                <option value="TEXT">Texte</option>
                                <option value="IMAGE">Image</option>
                                <option value="VIDEO">Vidéo</option>
                                <option value="DOCUMENT">Document</option>
                            </select>
                        </div>
                        {form.type_header === 'TEXT' && (
                            <div className="col-span-2">
                                <label className="block text-sm font-medium text-gray-700 mb-1">Texte du header</label>
                                <input name="contenu_header" value={form.contenu_header} onChange={handleChange} placeholder="ex: Offre spéciale !"
                                       className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400" />
                            </div>
                        )}
                        {headerEstMedia && (
                            <div className="col-span-2 grid grid-cols-3 gap-3">
                                <div className="col-span-2">
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Fichier header</label>
                                    <input type="file" onChange={(e) => { setHeaderFile(e.target.files?.[0] || null); setForm((prev) => ({ ...prev, header_handle: '' })) }}
                                           className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white" />
                                </div>
                                <div className="flex items-end">
                                    <button type="button" onClick={uploadHeaderMedia} disabled={uploadLoading || !headerFile}
                                            className="w-full px-4 py-2 bg-gray-800 text-white rounded-lg text-sm font-medium hover:bg-gray-900 disabled:opacity-50">
                                        {uploadLoading ? 'Upload...' : 'Uploader'}
                                    </button>
                                </div>
                                {form.header_handle && (
                                    <div className="col-span-3 text-xs text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2">
                                        Header handle Meta généré.
                                    </div>
                                )}
                            </div>
                        )}
                        <div className="col-span-2">
                            <label className="block text-sm font-medium text-gray-700 mb-1">Body</label>
                            <textarea name="contenu_body" value={form.contenu_body} onChange={handleChange}
                                      placeholder="ex: Bonjour {{1}}, profitez de {{2}}% de réduction." required rows={3}
                                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400" />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Footer</label>
                            <input name="contenu_footer" value={form.contenu_footer} onChange={handleChange} placeholder="ex: Répondez STOP pour vous désabonner."
                                   className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400" />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Exemples variables</label>
                            <input name="exemples_variables" value={form.exemples_variables} onChange={handleChange} placeholder="ex: Ikram, 30"
                                   className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400" />
                        </div>
                        <div className="col-span-2 border-t border-gray-100 pt-4">
                            <div className="flex items-center justify-between mb-3">
                                <h3 className="text-sm font-semibold text-gray-800">Boutons</h3>
                                <button type="button" onClick={ajouterBouton} disabled={form.boutons.length >= 3}
                                        className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg text-sm hover:bg-gray-200 disabled:opacity-50">
                                    + Ajouter bouton
                                </button>
                            </div>
                            <div className="grid gap-3">
                                {form.boutons.map((bouton, index) => (
                                    <div key={index} className="grid grid-cols-4 gap-3 bg-gray-50 border border-gray-100 rounded-lg p-3">
                                        <select value={bouton.type_bouton} onChange={(e) => handleBoutonChange(index, 'type_bouton', e.target.value)}
                                                className="border border-gray-200 rounded-lg px-3 py-2 text-sm">
                                            <option value="QUICK_REPLY">Réponse rapide</option>
                                            <option value="URL">Lien</option>
                                            <option value="PHONE_NUMBER">Téléphone</option>
                                        </select>
                                        <input value={bouton.texte} onChange={(e) => handleBoutonChange(index, 'texte', e.target.value)}
                                               placeholder="Texte" className="border border-gray-200 rounded-lg px-3 py-2 text-sm" />
                                        {bouton.type_bouton === 'URL' && (
                                            <input value={bouton.url} onChange={(e) => handleBoutonChange(index, 'url', e.target.value)}
                                                   placeholder="https://example.com" className="border border-gray-200 rounded-lg px-3 py-2 text-sm" />
                                        )}
                                        {bouton.type_bouton === 'PHONE_NUMBER' && (
                                            <input value={bouton.numero_telephone} onChange={(e) => handleBoutonChange(index, 'numero_telephone', e.target.value)}
                                                   placeholder="+212612345678" className="border border-gray-200 rounded-lg px-3 py-2 text-sm" />
                                        )}
                                        {bouton.type_bouton === 'QUICK_REPLY' && <div />}
                                        <button type="button" onClick={() => supprimerBouton(index)}
                                                className="px-3 py-2 bg-red-50 text-red-600 rounded-lg text-sm hover:bg-red-100">
                                            Supprimer
                                        </button>
                                    </div>
                                ))}
                            </div>
                        </div>
                        <div className="col-span-2 flex justify-end">
                            <button type="submit" disabled={formLoading || uploadLoading}
                                    className="px-6 py-2 bg-green-500 text-white rounded-lg text-sm font-medium hover:bg-green-600 disabled:opacity-50 transition-colors">
                                {formLoading ? 'Envoi en cours...' : 'Créer le template'}
                            </button>
                        </div>
                    </form>
                </div>
            )}

            {!loading && templates.length > 0 && (
                <BarreFiltres
                    filtres={filtres}
                    onChange={setFiltres}
                    statutsDisponibles={statutsDisponibles}
                    categoriesDisponibles={categoriesDisponibles}
                    languesDisponibles={languesDisponibles}
                    nbResultats={templatesFiltres.length}
                    nbTotal={templates.length}
                />
            )}

            {loading ? (
                <div className="flex flex-col items-center justify-center py-12">
                    <RefreshCw className="w-8 h-8 text-green-500 animate-spin mb-4" />
                    <p className="text-gray-500 font-medium">Chargement des templates...</p>
                </div>
            ) : templates.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                    <Inbox className="w-12 h-12 text-gray-300 mb-4" />
                    <p className="text-gray-500 font-medium mb-2">Aucun template trouvé</p>
                    <p className="text-gray-400 text-sm">Créez votre premier template pour commencer</p>
                </div>
            ) : templatesFiltres.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                    <Search className="w-12 h-12 text-gray-300 mb-4" />
                    <p className="text-gray-500 font-medium mb-2">Aucun résultat pour ces filtres</p>
                    <button
                        onClick={() => setFiltres(FILTRES_INITIAL)}
                        className="text-green-600 text-sm font-medium hover:underline mt-1"
                    >
                        Réinitialiser les filtres
                    </button>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                    {templatesFiltres.map((t) => (
                        <CarteTemplate
                            key={t.id}
                            template={t}
                            onOuvrir={setTemplateDetail}
                            onSupprimer={supprimerTemplate}
                        />
                    ))}
                </div>
            )}
        </div>
    )
}

export default Templates