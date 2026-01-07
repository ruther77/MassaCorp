import { useState } from 'react';
import {
  Wand2,
  Plus,
  Edit2,
  Trash2,
  Play,
  CheckCircle,
  AlertCircle,
  Tag,
  Settings,
} from 'lucide-react';
import { useExpenseCategories } from '../../hooks/useFinance';
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Button,
  Input,
  Select,
  Badge,
  Switch,
  Modal,
  ModalFooter,
  EmptyState,
  Alert,
} from '../../components/ui';
import { PageHeader } from '../../components/ui/Breadcrumb';

// Type pour les regles
interface CategorizationRule {
  id: number;
  name: string;
  keywords: string[];
  category_id: number;
  category_name: string;
  is_active: boolean;
  matches_count: number;
  created_at: string;
}

// Donnees mockees pour la demo
const mockRules: CategorizationRule[] = [
  {
    id: 1,
    name: 'Frais bancaires',
    keywords: ['FRAIS', 'COMMISSION', 'AGIOS'],
    category_id: 1,
    category_name: 'Frais bancaires',
    is_active: true,
    matches_count: 45,
    created_at: '2025-01-01',
  },
  {
    id: 2,
    name: 'Loyer mensuel',
    keywords: ['LOYER', 'SCI', 'BAIL'],
    category_id: 2,
    category_name: 'Loyer et charges',
    is_active: true,
    matches_count: 12,
    created_at: '2025-01-01',
  },
  {
    id: 3,
    name: 'Electricite',
    keywords: ['EDF', 'ENGIE', 'ELECTRICITE'],
    category_id: 3,
    category_name: 'Energie',
    is_active: false,
    matches_count: 8,
    created_at: '2025-01-01',
  },
];

export default function RulesPage() {
  const [rules, setRules] = useState<CategorizationRule[]>(mockRules);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isTestModalOpen, setIsTestModalOpen] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    keywords: '',
    category_id: '',
  });
  const [testText, setTestText] = useState('');
  const [testResults, setTestResults] = useState<{ rule: string; matched: boolean }[]>([]);

  const { data: categories } = useExpenseCategories();

  const categoryOptions = categories?.map(cat => ({
    value: cat.categorie_depense_id,
    label: cat.libelle,
  })) || [];

  const handleCreateRule = () => {
    const newRule: CategorizationRule = {
      id: Date.now(),
      name: formData.name,
      keywords: formData.keywords.split(',').map(k => k.trim().toUpperCase()),
      category_id: Number(formData.category_id),
      category_name: categories?.find(c => c.categorie_depense_id === Number(formData.category_id))?.libelle || '',
      is_active: true,
      matches_count: 0,
      created_at: new Date().toISOString(),
    };
    setRules(prev => [...prev, newRule]);
    setIsCreateModalOpen(false);
    setFormData({ name: '', keywords: '', category_id: '' });
  };

  const toggleRule = (id: number) => {
    setRules(prev =>
      prev.map(r => (r.id === id ? { ...r, is_active: !r.is_active } : r))
    );
  };

  const deleteRule = (id: number) => {
    setRules(prev => prev.filter(r => r.id !== id));
  };

  const testRules = () => {
    const results = rules.map(rule => ({
      rule: rule.name,
      matched: rule.keywords.some(kw => testText.toUpperCase().includes(kw)),
    }));
    setTestResults(results);
  };

  const activeRules = rules.filter(r => r.is_active);
  const inactiveRules = rules.filter(r => !r.is_active);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Regles de categorisation"
        subtitle="Automatisez la categorisation de vos transactions"
        breadcrumbs={[
          { label: 'Finance', href: '/finance' },
          { label: 'Regles' },
        ]}
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setIsTestModalOpen(true)}>
              <Play className="w-4 h-4 mr-2" />
              Tester
            </Button>
            <Button onClick={() => setIsCreateModalOpen(true)}>
              <Plus className="w-4 h-4 mr-2" />
              Nouvelle regle
            </Button>
          </div>
        }
      />

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">Regles actives</p>
                <p className="text-2xl font-bold text-green-400">{activeRules.length}</p>
              </div>
              <CheckCircle className="w-8 h-8 text-green-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">Regles inactives</p>
                <p className="text-2xl font-bold text-dark-400">{inactiveRules.length}</p>
              </div>
              <AlertCircle className="w-8 h-8 text-dark-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">Correspondances totales</p>
                <p className="text-2xl font-bold text-primary-400">
                  {rules.reduce((sum, r) => sum + r.matches_count, 0)}
                </p>
              </div>
              <Wand2 className="w-8 h-8 text-primary-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Info */}
      <Alert variant="info" title="Comment ca marche ?">
        Les regles de categorisation analysent le libelle de chaque transaction bancaire.
        Si l'un des mots-cles est trouve, la categorie correspondante est automatiquement appliquee.
      </Alert>

      {/* Liste des regles */}
      <Card>
        <CardHeader>
          <CardTitle subtitle={`${rules.length} regle(s) configuree(s)`}>
            <Settings className="w-5 h-5 inline mr-2" />
            Regles configurees
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {rules.length === 0 ? (
            <EmptyState
              icon={<Wand2 className="w-12 h-12" />}
              title="Aucune regle"
              description="Creez votre premiere regle de categorisation automatique."
              action={{
                label: 'Creer une regle',
                onClick: () => setIsCreateModalOpen(true),
              }}
            />
          ) : (
            <div className="divide-y divide-dark-700">
              {rules.map((rule) => (
                <div
                  key={rule.id}
                  className={`p-4 ${!rule.is_active ? 'opacity-50' : ''}`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <h3 className="font-medium text-white">{rule.name}</h3>
                        <Badge variant={rule.is_active ? 'success' : 'default'} size="sm">
                          {rule.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                        <Badge variant="info" size="sm">
                          {rule.matches_count} correspondances
                        </Badge>
                      </div>

                      <div className="flex items-center gap-2 mb-2">
                        <Tag className="w-4 h-4 text-dark-400" />
                        <span className="text-sm text-dark-300">
                          Categorie: <span className="text-white">{rule.category_name}</span>
                        </span>
                      </div>

                      <div className="flex flex-wrap gap-2">
                        {rule.keywords.map((kw, i) => (
                          <Badge key={i} variant="default" size="sm">
                            {kw}
                          </Badge>
                        ))}
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <Switch
                        checked={rule.is_active}
                        onChange={() => toggleRule(rule.id)}
                      />
                      <Button variant="ghost" size="sm">
                        <Edit2 className="w-4 h-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-red-400 hover:text-red-300"
                        onClick={() => deleteRule(rule.id)}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Modal creation */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Nouvelle regle de categorisation"
        size="md"
        footer={
          <ModalFooter
            onCancel={() => setIsCreateModalOpen(false)}
            onConfirm={handleCreateRule}
            cancelText="Annuler"
            confirmText="Creer la regle"
          />
        }
      >
        <div className="space-y-4">
          <Input
            label="Nom de la regle"
            value={formData.name}
            onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
            placeholder="Ex: Frais bancaires"
            required
          />
          <Input
            label="Mots-cles (separes par des virgules)"
            value={formData.keywords}
            onChange={(e) => setFormData(prev => ({ ...prev, keywords: e.target.value }))}
            placeholder="Ex: FRAIS, COMMISSION, AGIOS"
            required
          />
          <Select
            label="Categorie a appliquer"
            options={[{ value: '', label: 'Selectionnez une categorie' }, ...categoryOptions]}
            value={formData.category_id}
            onChange={(e) => setFormData(prev => ({ ...prev, category_id: e.target.value }))}
          />
        </div>
      </Modal>

      {/* Modal test */}
      <Modal
        isOpen={isTestModalOpen}
        onClose={() => setIsTestModalOpen(false)}
        title="Tester les regles"
        size="md"
        footer={
          <ModalFooter
            onCancel={() => setIsTestModalOpen(false)}
            cancelText="Fermer"
          />
        }
      >
        <div className="space-y-4">
          <Input
            label="Texte a analyser"
            value={testText}
            onChange={(e) => setTestText(e.target.value)}
            placeholder="Ex: PRLV FRAIS TENUE COMPTE"
          />
          <Button onClick={testRules} disabled={!testText}>
            <Play className="w-4 h-4 mr-2" />
            Tester
          </Button>

          {testResults.length > 0 && (
            <div className="space-y-2 pt-4 border-t border-dark-700">
              <p className="text-sm text-dark-400 mb-2">Resultats:</p>
              {testResults.map((result, i) => (
                <div
                  key={i}
                  className={`flex items-center justify-between p-2 rounded ${
                    result.matched ? 'bg-green-900/20' : 'bg-dark-700/50'
                  }`}
                >
                  <span className="text-sm text-white">{result.rule}</span>
                  {result.matched ? (
                    <Badge variant="success" size="sm">
                      <CheckCircle className="w-3 h-3 mr-1" />
                      Correspond
                    </Badge>
                  ) : (
                    <Badge variant="default" size="sm">
                      Non
                    </Badge>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
}
