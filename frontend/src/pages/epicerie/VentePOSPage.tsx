import { useState, useRef, useEffect, useCallback } from 'react';
import {
  ShoppingCart,
  Search,
  Plus,
  Minus,
  Trash2,
  CreditCard,
  Banknote,
  X,
  Check,
  AlertCircle,
  Package,
  Keyboard,
  Camera,
  CameraOff,
  SwitchCamera,
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { BrowserMultiFormatReader, NotFoundException } from '@zxing/library';
import apiClient from '@/api/client';
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Button,
  Input,
  Modal,
  ModalFooter,
  Badge,
} from '@/components/ui';
import { PageHeader } from '@/components/ui/Breadcrumb';
import { formatCurrency } from '@/lib/utils';

interface Product {
  id: number;
  ean: string;
  designation: string;
  prix_unitaire_moyen: string;
  taux_tva: string;
}

interface CartItem {
  product: Product;
  quantity: number;
  unitPrice: number;
}

type PaymentMethod = 'cash' | 'card';

// Detecte si la saisie ressemble a un code-barres (EAN)
const isBarcode = (value: string): boolean => {
  const cleaned = value.trim();
  return /^\d{8,14}$/.test(cleaned);
};

// Hook pour debounce
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => clearTimeout(handler);
  }, [value, delay]);

  return debouncedValue;
}

export default function VentePOSPage() {
  const [cart, setCart] = useState<CartItem[]>([]);
  const [searchInput, setSearchInput] = useState('');
  const [showResults, setShowResults] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('card');
  const [cashReceived, setCashReceived] = useState<number>(0);
  const [paymentSuccess, setPaymentSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSearching, setIsSearching] = useState(false);

  // Camera scanning state
  const [showCameraModal, setShowCameraModal] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [isCameraReady, setIsCameraReady] = useState(false);
  const [lastScannedCode, setLastScannedCode] = useState<string | null>(null);
  const [availableCameras, setAvailableCameras] = useState<MediaDeviceInfo[]>([]);
  const [selectedCameraIndex, setSelectedCameraIndex] = useState(0);

  const searchInputRef = useRef<HTMLInputElement>(null);
  const resultsRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const codeReaderRef = useRef<BrowserMultiFormatReader | null>(null);

  // Debounce la recherche (300ms)
  const debouncedSearch = useDebounce(searchInput, 300);

  // Recherche produits
  const { data: products = [], isFetching } = useQuery({
    queryKey: ['pos', 'products', debouncedSearch],
    queryFn: async () => {
      if (!debouncedSearch || debouncedSearch.length < 2) return [];
      setIsSearching(true);
      try {
        const response = await apiClient.get<{ items: Product[] }>('/metro/products', {
          params: { search: debouncedSearch, per_page: 15 },
        });
        return response.data.items || [];
      } finally {
        setIsSearching(false);
      }
    },
    enabled: debouncedSearch.length >= 2,
    staleTime: 30000,
  });

  // Focus sur l'input au chargement
  useEffect(() => {
    searchInputRef.current?.focus();
  }, []);

  // Reset selection quand les resultats changent
  useEffect(() => {
    setSelectedIndex(-1);
  }, [products]);

  // Afficher resultats quand on tape
  useEffect(() => {
    if (searchInput.length >= 2) {
      setShowResults(true);
    }
  }, [searchInput]);

  // Camera initialization
  useEffect(() => {
    if (showCameraModal) {
      initCamera();
    } else {
      stopCamera();
    }

    return () => {
      stopCamera();
    };
  }, [showCameraModal, selectedCameraIndex]);

  const initCamera = async () => {
    try {
      setCameraError(null);
      setIsCameraReady(false);

      // Get available cameras
      const devices = await navigator.mediaDevices.enumerateDevices();
      const cameras = devices.filter(device => device.kind === 'videoinput');
      setAvailableCameras(cameras);

      if (cameras.length === 0) {
        setCameraError('Aucune camera detectee');
        return;
      }

      // Create code reader
      const codeReader = new BrowserMultiFormatReader();
      codeReaderRef.current = codeReader;

      const selectedDeviceId = cameras[selectedCameraIndex]?.deviceId;

      // Start decoding
      await codeReader.decodeFromVideoDevice(
        selectedDeviceId,
        videoRef.current!,
        (result, err) => {
          if (result) {
            const code = result.getText();
            if (code !== lastScannedCode) {
              setLastScannedCode(code);
              handleScannedCode(code);
            }
          }
          if (err && !(err instanceof NotFoundException)) {
            console.error('Scan error:', err);
          }
        }
      );

      setIsCameraReady(true);
    } catch (err) {
      console.error('Camera init error:', err);
      if (err instanceof Error) {
        if (err.name === 'NotAllowedError') {
          setCameraError('Acces camera refuse. Autorisez l\'acces dans les parametres du navigateur.');
        } else if (err.name === 'NotFoundError') {
          setCameraError('Aucune camera trouvee sur cet appareil.');
        } else {
          setCameraError(`Erreur camera: ${err.message}`);
        }
      } else {
        setCameraError('Erreur lors de l\'initialisation de la camera');
      }
    }
  };

  const stopCamera = () => {
    if (codeReaderRef.current) {
      codeReaderRef.current.reset();
      codeReaderRef.current = null;
    }
    setIsCameraReady(false);
    setLastScannedCode(null);
  };

  const switchCamera = () => {
    if (availableCameras.length > 1) {
      setSelectedCameraIndex((prev) => (prev + 1) % availableCameras.length);
    }
  };

  const handleScannedCode = async (code: string) => {
    // Vibration feedback si disponible
    if ('vibrate' in navigator) {
      navigator.vibrate(100);
    }

    try {
      const response = await apiClient.get<{ items: Product[] }>('/metro/products', {
        params: { search: code, per_page: 1 },
      });

      if (response.data.items && response.data.items.length > 0) {
        addToCart(response.data.items[0]);
        setShowCameraModal(false);
      } else {
        setError(`Produit non trouve: ${code}`);
        setTimeout(() => setError(null), 3000);
        // Reset pour permettre nouveau scan
        setTimeout(() => setLastScannedCode(null), 1500);
      }
    } catch {
      setError('Erreur lors de la recherche');
      setTimeout(() => setError(null), 3000);
      setTimeout(() => setLastScannedCode(null), 1500);
    }
  };

  // Calculs panier
  const subtotal = cart.reduce((sum, item) => sum + item.unitPrice * item.quantity, 0);
  const totalTVA = cart.reduce((sum, item) => {
    const tva = parseFloat(item.product.taux_tva) || 20;
    return sum + (item.unitPrice * item.quantity * tva) / 100;
  }, 0);
  const total = subtotal + totalTVA;
  const change = cashReceived - total;
  const itemCount = cart.reduce((sum, item) => sum + item.quantity, 0);

  // Ajouter au panier
  const addToCart = useCallback((product: Product) => {
    setCart((prev) => {
      const existingItem = prev.find((item) => item.product.ean === product.ean);
      if (existingItem) {
        return prev.map((item) =>
          item.product.ean === product.ean
            ? { ...item, quantity: item.quantity + 1 }
            : item
        );
      }
      return [
        ...prev,
        {
          product,
          quantity: 1,
          unitPrice: parseFloat(product.prix_unitaire_moyen) || 0,
        },
      ];
    });
    setSearchInput('');
    setShowResults(false);
    setSelectedIndex(-1);
    searchInputRef.current?.focus();
  }, []);

  // Recherche par code-barres (Enter)
  const searchByBarcode = useCallback(async (barcode: string) => {
    if (!barcode) return;

    setError(null);
    setIsSearching(true);

    try {
      const response = await apiClient.get<{ items: Product[] }>('/metro/products', {
        params: { search: barcode, per_page: 1 },
      });

      if (response.data.items && response.data.items.length > 0) {
        addToCart(response.data.items[0]);
      } else {
        setError(`Produit non trouve: ${barcode}`);
        setTimeout(() => setError(null), 3000);
      }
    } catch {
      setError('Erreur lors de la recherche');
      setTimeout(() => setError(null), 3000);
    } finally {
      setIsSearching(false);
      setSearchInput('');
    }
  }, [addToCart]);

  // Gestion clavier
  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
    const resultsCount = products.length;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        if (showResults && resultsCount > 0) {
          setSelectedIndex((prev) => (prev + 1) % resultsCount);
        }
        break;

      case 'ArrowUp':
        e.preventDefault();
        if (showResults && resultsCount > 0) {
          setSelectedIndex((prev) => (prev - 1 + resultsCount) % resultsCount);
        }
        break;

      case 'Enter':
        e.preventDefault();
        if (selectedIndex >= 0 && products[selectedIndex]) {
          addToCart(products[selectedIndex]);
        } else if (isBarcode(searchInput)) {
          searchByBarcode(searchInput);
        } else if (products.length === 1) {
          addToCart(products[0]);
        }
        break;

      case 'Escape':
        setShowResults(false);
        setSelectedIndex(-1);
        break;

      case 'Tab':
        if (showResults) {
          e.preventDefault();
          if (resultsCount > 0) {
            setSelectedIndex((prev) => (prev + 1) % resultsCount);
          }
        }
        break;
    }
  }, [showResults, products, selectedIndex, searchInput, addToCart, searchByBarcode]);

  // Mettre a jour quantite
  const updateQuantity = (ean: string, delta: number) => {
    setCart((prev) =>
      prev
        .map((item) =>
          item.product.ean === ean
            ? { ...item, quantity: Math.max(0, item.quantity + delta) }
            : item
        )
        .filter((item) => item.quantity > 0)
    );
  };

  // Supprimer item
  const removeItem = (ean: string) => {
    setCart((prev) => prev.filter((item) => item.product.ean !== ean));
  };

  // Vider panier
  const clearCart = () => {
    setCart([]);
    searchInputRef.current?.focus();
  };

  // Traiter paiement
  const processPayment = () => {
    setTimeout(() => {
      setPaymentSuccess(true);
      setTimeout(() => {
        setShowPaymentModal(false);
        setPaymentSuccess(false);
        setCart([]);
        setCashReceived(0);
        searchInputRef.current?.focus();
      }, 2000);
    }, 1000);
  };

  // Fermer resultats si clic ailleurs
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        resultsRef.current &&
        !resultsRef.current.contains(e.target as Node) &&
        searchInputRef.current &&
        !searchInputRef.current.contains(e.target as Node)
      ) {
        setShowResults(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="space-y-4">
      <PageHeader
        title="Vente POS"
        subtitle="Point de vente - Scannez ou recherchez un produit"
        breadcrumbs={[
          { label: 'Epicerie', href: '/epicerie' },
          { label: 'Vente POS' },
        ]}
      />

      {/* Message d'erreur */}
      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-500/20 border border-red-500/50 rounded-lg text-red-400 animate-pulse">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ml-auto">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Gauche: Recherche unifiee */}
        <div className="lg:col-span-2 space-y-4">
          {/* Barre de recherche principale */}
          <Card className="overflow-visible">
            <CardContent className="py-4">
              <div className="flex gap-3">
                {/* Input principal */}
                <div className="relative flex-1">
                  <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-dark-400" />
                  <input
                    ref={searchInputRef}
                    type="text"
                    placeholder="Scannez un code-barres ou tapez le nom..."
                    value={searchInput}
                    onChange={(e) => setSearchInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    onFocus={() => searchInput.length >= 2 && setShowResults(true)}
                    className="w-full pl-12 pr-20 py-4 text-lg bg-dark-800 border-2 border-dark-600 rounded-xl
                             text-white placeholder-dark-400
                             focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 focus:outline-none
                             transition-all"
                  />
                  {/* Indicateurs */}
                  <div className="absolute right-4 top-1/2 -translate-y-1/2 flex items-center gap-2">
                    {isSearching || isFetching ? (
                      <div className="w-5 h-5 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
                    ) : searchInput ? (
                      <button
                        onClick={() => {
                          setSearchInput('');
                          setShowResults(false);
                          searchInputRef.current?.focus();
                        }}
                        className="p-1 hover:bg-dark-700 rounded-full transition-colors"
                      >
                        <X className="w-5 h-5 text-dark-400" />
                      </button>
                    ) : null}
                    {isBarcode(searchInput) && (
                      <Badge variant="info" size="sm">EAN</Badge>
                    )}
                  </div>

                  {/* Dropdown resultats */}
                  {showResults && searchInput.length >= 2 && (
                    <div
                      ref={resultsRef}
                      className="absolute top-full left-0 right-0 mt-2 bg-dark-800 border border-dark-600
                               rounded-xl shadow-2xl overflow-hidden z-50 max-h-96 overflow-y-auto"
                    >
                      {products.length > 0 ? (
                        <div className="divide-y divide-dark-700">
                          {products.map((product, index) => (
                            <button
                              key={product.id}
                              onClick={() => addToCart(product)}
                              onMouseEnter={() => setSelectedIndex(index)}
                              className={`w-full flex items-center gap-4 p-4 text-left transition-colors ${
                                selectedIndex === index
                                  ? 'bg-primary-500/20 border-l-4 border-primary-500'
                                  : 'hover:bg-dark-700/50 border-l-4 border-transparent'
                              }`}
                            >
                              <div className="w-10 h-10 bg-dark-700 rounded-lg flex items-center justify-center flex-shrink-0">
                                <Package className="w-5 h-5 text-dark-400" />
                              </div>
                              <div className="flex-1 min-w-0">
                                <p className="font-medium text-white truncate">
                                  {product.designation}
                                </p>
                                <p className="text-sm text-dark-400 font-mono">
                                  {product.ean}
                                </p>
                              </div>
                              <div className="text-right flex-shrink-0">
                                <p className="font-bold text-green-400 text-lg">
                                  {formatCurrency(parseFloat(product.prix_unitaire_moyen))}
                                </p>
                                <p className="text-xs text-dark-400">
                                  TVA {product.taux_tva}%
                                </p>
                              </div>
                              {selectedIndex === index && (
                                <div className="text-xs text-dark-400 bg-dark-700 px-2 py-1 rounded">
                                  Entree
                                </div>
                              )}
                            </button>
                          ))}
                        </div>
                      ) : !isFetching && !isSearching ? (
                        <div className="p-8 text-center">
                          <Package className="w-12 h-12 mx-auto mb-3 text-dark-500" />
                          <p className="text-dark-400">Aucun produit trouve</p>
                          <p className="text-sm text-dark-500 mt-1">
                            Essayez un autre terme ou scannez le code-barres
                          </p>
                        </div>
                      ) : null}
                    </div>
                  )}
                </div>

                {/* Bouton camera */}
                <Button
                  variant="secondary"
                  className="h-[58px] px-5"
                  onClick={() => setShowCameraModal(true)}
                  title="Scanner avec la camera"
                >
                  <Camera className="w-6 h-6" />
                </Button>
              </div>

              {/* Aide raccourcis */}
              <div className="flex items-center gap-4 mt-3 text-xs text-dark-500">
                <div className="flex items-center gap-1">
                  <Keyboard className="w-3 h-3" />
                  <span>Navigation:</span>
                </div>
                <span className="px-1.5 py-0.5 bg-dark-700 rounded">↑↓</span>
                <span>Selectionner</span>
                <span className="px-1.5 py-0.5 bg-dark-700 rounded">Entree</span>
                <span>Ajouter</span>
                <span className="px-1.5 py-0.5 bg-dark-700 rounded">Echap</span>
                <span>Fermer</span>
                <span className="ml-auto flex items-center gap-1">
                  <Camera className="w-3 h-3" />
                  Ou utilisez la camera
                </span>
              </div>
            </CardContent>
          </Card>

          {/* Zone vide - suggestions futures */}
          {cart.length === 0 && (
            <Card className="border-dashed">
              <CardContent className="py-12 text-center">
                <ShoppingCart className="w-16 h-16 mx-auto mb-4 text-dark-600" />
                <h3 className="text-lg font-medium text-dark-300 mb-2">
                  Pret pour la vente
                </h3>
                <p className="text-dark-500 max-w-md mx-auto mb-4">
                  Scannez un code-barres avec votre lecteur, utilisez la camera,
                  ou tapez le nom du produit dans la barre de recherche.
                </p>
                <Button
                  variant="secondary"
                  onClick={() => setShowCameraModal(true)}
                >
                  <Camera className="w-4 h-4 mr-2" />
                  Ouvrir la camera
                </Button>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Droite: Panier */}
        <div className="space-y-4">
          <Card className="sticky top-4">
            <CardHeader className="border-b border-dark-700">
              <div className="flex items-center justify-between">
                <CardTitle>
                  <ShoppingCart className="w-5 h-5 inline mr-2" />
                  Panier
                  {itemCount > 0 && (
                    <Badge variant="primary" size="sm" className="ml-2">
                      {itemCount} article{itemCount > 1 ? 's' : ''}
                    </Badge>
                  )}
                </CardTitle>
                {cart.length > 0 && (
                  <Button variant="ghost" size="sm" onClick={clearCart} title="Vider le panier">
                    <Trash2 className="w-4 h-4" />
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {cart.length === 0 ? (
                <div className="text-center py-12 text-dark-400">
                  <ShoppingCart className="w-12 h-12 mx-auto mb-3 opacity-30" />
                  <p className="font-medium">Panier vide</p>
                  <p className="text-sm text-dark-500">Ajoutez des produits</p>
                </div>
              ) : (
                <>
                  {/* Liste des items */}
                  <div className="divide-y divide-dark-700 max-h-80 overflow-y-auto">
                    {cart.map((item) => (
                      <div
                        key={item.product.ean}
                        className="flex items-center gap-3 p-3 hover:bg-dark-700/30 transition-colors"
                      >
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-white text-sm truncate">
                            {item.product.designation}
                          </p>
                          <p className="text-xs text-dark-400">
                            {formatCurrency(item.unitPrice)} / unite
                          </p>
                        </div>
                        <div className="flex items-center gap-1 bg-dark-700 rounded-lg p-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => updateQuantity(item.product.ean, -1)}
                            className="h-7 w-7 p-0"
                          >
                            <Minus className="w-3 h-3" />
                          </Button>
                          <span className="w-8 text-center font-bold text-white">
                            {item.quantity}
                          </span>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => updateQuantity(item.product.ean, 1)}
                            className="h-7 w-7 p-0"
                          >
                            <Plus className="w-3 h-3" />
                          </Button>
                        </div>
                        <div className="w-20 text-right">
                          <p className="font-bold text-white">
                            {formatCurrency(item.unitPrice * item.quantity)}
                          </p>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-red-400 hover:text-red-300 hover:bg-red-500/20 h-7 w-7 p-0"
                          onClick={() => removeItem(item.product.ean)}
                        >
                          <X className="w-4 h-4" />
                        </Button>
                      </div>
                    ))}
                  </div>

                  {/* Totaux */}
                  <div className="p-4 bg-dark-700/30 space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-dark-400">Sous-total HT</span>
                      <span className="text-white">{formatCurrency(subtotal)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-dark-400">TVA</span>
                      <span className="text-orange-400">+{formatCurrency(totalTVA)}</span>
                    </div>
                    <div className="flex justify-between text-xl font-bold pt-3 border-t border-dark-600">
                      <span className="text-white">Total TTC</span>
                      <span className="text-green-400">{formatCurrency(total)}</span>
                    </div>
                  </div>

                  {/* Bouton paiement */}
                  <div className="p-4 pt-0">
                    <Button
                      className="w-full py-4 text-lg"
                      size="lg"
                      onClick={() => setShowPaymentModal(true)}
                    >
                      <CreditCard className="w-5 h-5 mr-2" />
                      Encaisser {formatCurrency(total)}
                    </Button>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Modal Camera Scanner */}
      <Modal
        isOpen={showCameraModal}
        onClose={() => setShowCameraModal(false)}
        title="Scanner un code-barres"
        size="lg"
      >
        <div className="space-y-4">
          {/* Zone video */}
          <div className="relative bg-black rounded-xl overflow-hidden aspect-video">
            <video
              ref={videoRef}
              className="w-full h-full object-cover"
              playsInline
              muted
            />

            {/* Overlay de scan */}
            {isCameraReady && (
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div className="w-64 h-32 border-2 border-primary-500 rounded-lg relative">
                  <div className="absolute -top-1 -left-1 w-4 h-4 border-t-2 border-l-2 border-primary-400" />
                  <div className="absolute -top-1 -right-1 w-4 h-4 border-t-2 border-r-2 border-primary-400" />
                  <div className="absolute -bottom-1 -left-1 w-4 h-4 border-b-2 border-l-2 border-primary-400" />
                  <div className="absolute -bottom-1 -right-1 w-4 h-4 border-b-2 border-r-2 border-primary-400" />
                  <div className="absolute top-1/2 left-0 right-0 h-0.5 bg-red-500/50 animate-pulse" />
                </div>
              </div>
            )}

            {/* Loading */}
            {!isCameraReady && !cameraError && (
              <div className="absolute inset-0 flex items-center justify-center bg-dark-900">
                <div className="text-center">
                  <div className="w-12 h-12 border-4 border-primary-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                  <p className="text-dark-400">Initialisation de la camera...</p>
                </div>
              </div>
            )}

            {/* Error */}
            {cameraError && (
              <div className="absolute inset-0 flex items-center justify-center bg-dark-900">
                <div className="text-center p-6">
                  <CameraOff className="w-16 h-16 mx-auto mb-4 text-red-500" />
                  <p className="text-red-400 mb-4">{cameraError}</p>
                  <Button variant="secondary" onClick={initCamera}>
                    Reessayer
                  </Button>
                </div>
              </div>
            )}

            {/* Camera switch button */}
            {availableCameras.length > 1 && isCameraReady && (
              <button
                onClick={switchCamera}
                className="absolute top-3 right-3 p-2 bg-black/50 hover:bg-black/70 rounded-full transition-colors"
                title="Changer de camera"
              >
                <SwitchCamera className="w-5 h-5 text-white" />
              </button>
            )}
          </div>

          {/* Instructions */}
          <div className="text-center text-dark-400 text-sm">
            <p>Placez le code-barres dans le cadre</p>
            <p className="text-xs mt-1">Le scan est automatique</p>
          </div>

          {/* Last scanned */}
          {lastScannedCode && (
            <div className="flex items-center justify-center gap-2 p-3 bg-primary-500/20 rounded-lg">
              <Check className="w-5 h-5 text-primary-400" />
              <span className="text-primary-400 font-mono">{lastScannedCode}</span>
              <span className="text-dark-400">scanne</span>
            </div>
          )}

          {/* Boutons */}
          <div className="flex gap-3">
            <Button
              variant="secondary"
              className="flex-1"
              onClick={() => setShowCameraModal(false)}
            >
              Fermer
            </Button>
            {!isCameraReady && cameraError && (
              <Button className="flex-1" onClick={initCamera}>
                Reessayer
              </Button>
            )}
          </div>
        </div>
      </Modal>

      {/* Modal Paiement */}
      <Modal
        isOpen={showPaymentModal}
        onClose={() => !paymentSuccess && setShowPaymentModal(false)}
        title={paymentSuccess ? 'Paiement reussi' : 'Encaissement'}
        size="md"
      >
        {paymentSuccess ? (
          <div className="text-center py-8">
            <div className="w-20 h-20 mx-auto mb-4 rounded-full bg-green-500/20 flex items-center justify-center">
              <Check className="w-10 h-10 text-green-400" />
            </div>
            <p className="text-2xl font-bold text-white">Paiement accepte</p>
            <p className="text-dark-400 mt-2 text-lg">
              {formatCurrency(total)}
            </p>
            {paymentMethod === 'cash' && change > 0 && (
              <div className="mt-4 p-4 bg-yellow-500/20 rounded-lg">
                <p className="text-sm text-yellow-400">Monnaie a rendre</p>
                <p className="text-2xl font-bold text-yellow-400">
                  {formatCurrency(change)}
                </p>
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-6">
            {/* Total */}
            <div className="text-center py-6 bg-gradient-to-br from-dark-700 to-dark-800 rounded-xl">
              <p className="text-sm text-dark-400 mb-1">Total a encaisser</p>
              <p className="text-4xl font-bold text-green-400">{formatCurrency(total)}</p>
              <p className="text-sm text-dark-500 mt-1">{itemCount} article{itemCount > 1 ? 's' : ''}</p>
            </div>

            {/* Mode de paiement */}
            <div className="space-y-3">
              <p className="text-sm font-medium text-dark-300">Mode de paiement</p>
              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => setPaymentMethod('card')}
                  className={`flex flex-col items-center gap-3 p-6 rounded-xl border-2 transition-all ${
                    paymentMethod === 'card'
                      ? 'border-primary-500 bg-primary-500/10 shadow-lg shadow-primary-500/20'
                      : 'border-dark-600 hover:border-dark-500 hover:bg-dark-700/50'
                  }`}
                >
                  <CreditCard
                    className={`w-10 h-10 ${
                      paymentMethod === 'card' ? 'text-primary-400' : 'text-dark-400'
                    }`}
                  />
                  <span
                    className={`font-medium ${
                      paymentMethod === 'card' ? 'text-white' : 'text-dark-400'
                    }`}
                  >
                    Carte bancaire
                  </span>
                </button>
                <button
                  onClick={() => setPaymentMethod('cash')}
                  className={`flex flex-col items-center gap-3 p-6 rounded-xl border-2 transition-all ${
                    paymentMethod === 'cash'
                      ? 'border-green-500 bg-green-500/10 shadow-lg shadow-green-500/20'
                      : 'border-dark-600 hover:border-dark-500 hover:bg-dark-700/50'
                  }`}
                >
                  <Banknote
                    className={`w-10 h-10 ${
                      paymentMethod === 'cash' ? 'text-green-400' : 'text-dark-400'
                    }`}
                  />
                  <span
                    className={`font-medium ${
                      paymentMethod === 'cash' ? 'text-white' : 'text-dark-400'
                    }`}
                  >
                    Especes
                  </span>
                </button>
              </div>
            </div>

            {/* Saisie especes */}
            {paymentMethod === 'cash' && (
              <div className="space-y-4">
                <Input
                  type="number"
                  label="Montant recu"
                  value={cashReceived || ''}
                  onChange={(e) => setCashReceived(Number(e.target.value))}
                  placeholder="0.00"
                  step="0.01"
                  min="0"
                  className="text-lg"
                />
                {/* Boutons montants rapides */}
                <div className="flex gap-2 flex-wrap">
                  {[5, 10, 20, 50].map((amount) => (
                    <Button
                      key={amount}
                      variant="secondary"
                      size="sm"
                      onClick={() => setCashReceived(amount)}
                    >
                      {amount} EUR
                    </Button>
                  ))}
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setCashReceived(Math.ceil(total))}
                  >
                    Arrondi ({Math.ceil(total)} EUR)
                  </Button>
                </div>
                {cashReceived >= total && (
                  <div className="flex justify-between p-4 bg-green-500/20 rounded-xl border border-green-500/30">
                    <span className="text-green-400 font-medium">Monnaie a rendre</span>
                    <span className="font-bold text-green-400 text-xl">
                      {formatCurrency(change)}
                    </span>
                  </div>
                )}
                {cashReceived > 0 && cashReceived < total && (
                  <div className="flex justify-between p-4 bg-red-500/20 rounded-xl border border-red-500/30">
                    <span className="text-red-400 font-medium">Montant insuffisant</span>
                    <span className="font-bold text-red-400">
                      -{formatCurrency(total - cashReceived)}
                    </span>
                  </div>
                )}
              </div>
            )}

            <ModalFooter
              onCancel={() => setShowPaymentModal(false)}
              onConfirm={() => {
                if (paymentMethod === 'cash' && cashReceived < total) return;
                processPayment();
              }}
              cancelText="Annuler"
              confirmText={
                paymentMethod === 'card'
                  ? 'Valider paiement CB'
                  : cashReceived >= total
                    ? 'Valider paiement'
                    : 'Montant insuffisant'
              }
            />
          </div>
        )}
      </Modal>
    </div>
  );
}
