#!/usr/bin/env python3
"""
Classificateur automatique de produits pour NOUTAM SAS
Assigne une catégorie à chaque produit basé sur des patterns de reconnaissance
"""

import re
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

# =============================================================================
# RÈGLES DE CLASSIFICATION (ordre de priorité)
# =============================================================================

CLASSIFICATION_RULES: Dict[str, List[str]] = {
    # =========================================================================
    # ALCOOLS (priorité haute pour éviter confusion avec autres boissons)
    # =========================================================================
    'ALC_SPIRIT': [
        r'\b(WHISKY|WHISKEY|VODKA|RHUM|RUM|GIN\b|COGNAC|ARMAGNAC|CALVADOS|TEQUILA|MEZCAL)',
        r'\b(ABSOLUT|BACARDI|BAILEYS|SMIRNOFF|JACK DANIEL|JOHNNIE|BALLANTINE|BELVEDERE)',
        r'\b(GREY GOOSE|HENNESSY|MARTELL|REMY MARTIN|HAVANA|CAPTAIN MORGAN|MALIBU)',
        r'\b(PASTIS|RICARD|PERNOD|51|GET 27|CHARTREUSE|BENEDICTINE)',
        r'\b\d{2}D\s+\d+CL\b',  # Pattern "40D 70CL"
    ],
    'ALC_VIN_RGE': [
        r'\b(BORDEAUX|BDX)\s*(RGE|ROUGE)',
        r'\b(MEDOC|HAUT.?MEDOC|MARGAUX|PAUILLAC|SAINT.?EMILION|POMEROL|GRAVES)',
        r'\b(BOURGOGNE|BRG).*\b(RGE|ROUGE|PINOT)',
        r'\bROUGE\b.*\b(75CL|AOC|AOP|IGP)',
        r'\b(COTES.?DU.?RHONE|CHATEAUNEUF|GIGONDAS|VACQUEYRAS).*\bRGE',
        r'\b(BEAUJOLAIS|BROUILLY|MORGON|FLEURIE)',
        r'\bCH\s+[A-Z]+.*75CL\s+T\b',  # Pattern château
    ],
    'ALC_VIN_BLC': [
        r'\b(CHABLIS|CHARDONNAY|SAUVIGNON|MUSCADET|SANCERRE|POUILLY)',
        r'\b(BLANC|BLC)\s.*\b(75CL|AOC|AOP|IGP)',
        r'\bALSACE\b.*\b(RIESLING|GEWURZ|PINOT)',
        r'\bBOURGOGNE.*\bBLC',
    ],
    'ALC_VIN_ROSE': [
        r'\b(ROSE|RSE)\b.*\b(75CL|AOC|AOP|IGP)',
        r'\bPROVENCE\b',
        r'\bTAVEL\b',
    ],
    'ALC_BIERE': [
        r'\b(BIERE|HEINEKEN|KRONENBOURG|LEFFE|GRIMBERGEN|DESPERADOS)',
        r'\b(CORONA|BUDWEISER|1664|AFFLIGEM|HOEGAARDEN|STELLA|AMSTEL)',
        r'\b(CARLSBERG|JUPILER|PELFORTH|CHOUFFE|DUVEL|CHIMAY)',
        r'\bBAVR\b',
        r'\b\d+D\s+\d+X?\d*CL\s+B\b',  # Pattern "5D 33CL B"
    ],
    'ALC_APERO': [
        r'\b(PORTO|MARTINI|CINZANO|LILLET|DUBONNET|VERMOUTH)',
        r'\b(KIR|CASSIS|PINEAU|FLOC)',
        r'\b(APEROL|CAMPARI|SUZE|AMER)',
    ],
    'ALC_LIQUEUR': [
        r'\b(COINTREAU|GRAND MARNIER|CURACAO|TRIPLE SEC)',
        r'\b(AMARETTO|LIMONCELLO|SAMBUCA|KAHLUA)',
        r'\b(CREME DE|LIQUEUR)',
    ],
    
    # =========================================================================
    # BOISSONS SANS ALCOOL
    # =========================================================================
    'BOIS_SODA': [
        r'\b(COCA.?COLA|PEPSI|7UP|FANTA|SPRITE|ORANGINA|SCHWEPPES)',
        r'\b(OASIS|ICE TEA|LIPTON|FUZE TEA)',
        r'\bDR.?PEPPER\b',
    ],
    'BOIS_EAU': [
        r'\b(EVIAN|VITTEL|VOLVIC|CRISTALINE|PERRIER|BADOIT)',
        r'\b(SAN PELLEGRINO|CONTREX|HEPAR|COURMAYEUR)',
        r'\bEAU\s+(MINERALE|DE SOURCE|GAZEUSE|PLATE)',
    ],
    'BOIS_JUS': [
        r'\b(JUS|NECTAR|SMOOTHIE)\s+(DE|D\')',
        r'\bPUR\s+JUS\b',
        r'\b(TROPICANA|JOKER|PAMPRYL|INNOCENT|PAGO)',
        r'\b(ORANGE|POMME|MULTIFRUITS|RAISIN).*JUS',
    ],
    'BOIS_SIROP': [
        r'\bSIROP\b',
        r'\b(TEISSEIRE|MOULIN.?DE.?VALDONNE|GILBERT.*SIROP)',
        r'\b(GRENADINE|MENTHE|CITRON|FRAISE).*\d+L\b.*(?!YAOURT|YOP)',
    ],
    'BOIS_ENERG': [
        r'\b(MONSTER|RED BULL|BURN|ROCKSTAR)\b',
        r'\bENERGY\s+DRINK\b',
    ],
    
    # =========================================================================
    # BOISSONS CHAUDES
    # =========================================================================
    'BOIS_CAFE': [
        r'\bCAFE\b(?!.*GOURMAND)',
        r'\b(ARABICA|ROBUSTA|EXPRESSO|ESPRESSO)',
        r'\b(MOULU|GRAINS|DOSETTE|CAPSULE)',
        r'\b(CARTE NOIRE|GRAND MERE|LAVAZZA|ILLY|NESPRESSO|SENSEO)',
        r'\b(DOLCE GUSTO|TASSIMO)',
        r'\bNESCAFE\b',
    ],
    'BOIS_THE': [
        r'\bTHE\s+(VERT|NOIR|BLANC|EARL|ENGLISH)',
        r'\b(INFUSION|TISANE|ROOIBOS)',
        r'\b(CAMOMILLE|VERVEINE|TILLEUL)',
        r'\b(TWININGS|ELEPHANT|TETLEY|KUSMI)',
    ],
    'BOIS_CHOCO': [
        r'\bCHOCOLAT\s+(EN POUDRE|CHAUD)',
        r'\b(POULAIN|VAN HOUTEN|BANANIA|NESQUIK)\b(?!.*CEREALE)',
    ],
    
    # =========================================================================
    # PRODUITS LAITIERS
    # =========================================================================
    'LAIT_UHT': [
        r'\bLAIT\s+(UHT|ENTIER|ECREME|1/2|DEMI)',
        r'\b(LACTEL|CANDIA|BRIDEL|PRESIDENT).*LAIT',
        r'\bLAIT\b.*\b1L\b',
    ],
    'LAIT_CREME': [
        r'\bCREME\s+(FRAICHE|LIQUIDE|UHT|EPAISSE|FLEURETTE)',
        r'\bCREME\s+\d+%',
        r'\b(MASCARPONE|CHANTILLY)',
        r'\bCREME\b.*\b(20CL|50CL|1L|35%)\b',
    ],
    'LAIT_BEURRE': [
        r'\bBEURRE\b(?!.*PETIT)',
        r'\b(MARGARINE|PLANTA|PRIMEVERE)',
        r'\b(PRESIDENT|ELLE.?VIRE|PAYSAN).*BEURRE',
    ],
    'LAIT_FROMAGE': [
        r'\bFROMAGE\b',
        r'\b(EMMENTAL|GRUYERE|COMTE|BEAUFORT|PARMESAN|GRANA)',
        r'\b(CAMEMBERT|BRIE|COULOMMIERS|CHAOURCE)',
        r'\b(ROQUEFORT|BLEU|FOURME|GORGONZOLA)',
        r'\b(CHEVRE|FETA|MOZZARELLA|RICOTTA|BURRATA)',
        r'\b(RACLETTE|FONDUE|REBLOCHON|MONT D\'OR)',
        r'\b(KIRI|VACHE QUI RIT|BABYBEL|CAPRICE)',
        r'\b(BOURSIN|PHILADELPHIA|TARTARE|ST MORET)',
        r'\bRAPE\s+\d+G',
    ],
    'LAIT_YAOURT': [
        r'\b(YAOURT|YOGOURT|YOPLAIT)\b',
        r'\b(DANONE|ACTIVIA|DANETTE|FJORD|SKYR|YOP)',
        r'\bFROMAGE\s+BLANC\b',
        r'\bPETIT\s+SUISSE\b',
    ],
    'LAIT_DESSERT': [
        r'\bCREME\s+DESSERT\b',
        r'\b(FLAN|LIÉGEOIS|MOUSSE|PANNA COTTA)',
        r'\bDESSERT\s+LACTE\b',
    ],
    
    # =========================================================================
    # ÉPICERIE SALÉE - FÉCULENTS
    # =========================================================================
    'EPIC_PATE': [
        r'\b(SPAGHETTI|TAGLIATELLE|PENNE|FUSILLI|FARFALLE)',
        r'\b(LASAGNE|CANNELLONI|RAVIOLI|TORTELLINI)',
        r'\b(COQUILLETTE|MACARONI|TORSADE|PAPILLON)',
        r'\b(BARILLA|PANZANI|LUSTUCRU|DE CECCO).*PATE',
        r'\bPATE\s+(FRAICHE|ALIMENTAIRE)',
    ],
    'EPIC_RIZ': [
        r'\bRIZ\s+(BASMATI|LONG|THAI|ARBORIO|COMPLET|ROND)',
        r'\b(UNCLE BEN|TAUREAU AILE).*RIZ',
        r'\bRIZ\s+\d+KG',
        r'\bRISOTTO\b',
    ],
    'EPIC_SEMOULE': [
        r'\bSEMOUL',
        r'\bCOUSCOUS\b',
        r'\b(QUINOA|BOULGOUR|EBLY|POLENTA)',
    ],
    'EPIC_LEGUM_SEC': [
        r'\b(LENTILLE|POIS CHICHE|HARICOT SEC|FLAGEOLET)',
        r'\b(FEVE|POIS CASSE|MONGETTE)',
        r'\bLEGUMINEUSE',
    ],
    
    # =========================================================================
    # ÉPICERIE SALÉE - CONSERVES
    # =========================================================================
    'CONS_LEGUME': [
        r'\b(PETIT.?POIS|MAIS DOUX|HARICOT VERT).*\b(BTE|BOITE|CONSERVE)',
        r'\b(TOMATE|CHAMPIGNON|OLIVE|CORNICHON).*\b(PELEE|CONCASSE|BTE)',
        r'\b(ARTICHAUT|ASPERGE|COEUR DE PALMIER|BETTERAVE).*\bBTE',
        r'\bBONDUELLE\b',
    ],
    'CONS_POISSON': [
        r'\b(THON|SARDINE|MAQUEREAU|ANCHOIS).*\b(BTE|BOITE|CONSERVE|HUILE)',
        r'\b(SAUPIQUET|PETIT NAVIRE|CONNETABLE)',
        r'\bMIETTE\s+DE\b',
    ],
    'CONS_PLAT': [
        r'\b(CASSOULET|CHOUCROUTE|BLANQUETTE|BOURGUIGNON)',
        r'\b(PETIT SALE|POT AU FEU|TRIPES)',
        r'\b(RAVIOLI|CANNELLONI).*\b(BTE|BOITE)',
        r'\bBELLE F.*(CASSOULET|RAVIOLI|CHOUCROUTE)',
    ],
    'CONS_SAUCE': [
        r'\bSAUCE\s+(TOMATE|BOLOGNAISE|CARBONARA|NAPOLITAINE)',
        r'\b(COULIS|PULPE|PASSATA|CONCENTRE)\s+TOMATE',
        r'\b(PESTO|PISTOU)',
        r'\bMUTTI\b',
    ],
    
    # =========================================================================
    # ÉPICERIE SALÉE - CONDIMENTS
    # =========================================================================
    'COND_HUILE': [
        r'\bHUILE\s+(OLIVE|TOURNESOL|COLZA|ARACHIDE|SESAME|FRITURE)',
        r'\b(LESIEUR|PUGET|CARAPELLI).*HUILE',
        r'\bHUILE\s+\d+L\b',
        r'\bFRITURE\s+\d+L\b',
    ],
    'COND_VINAIGRE': [
        r'\bVINAIGRE\s+(BALSAMIQUE|VIN|CIDRE|XERES|BLANC)',
        r'\bMODENE\b',
    ],
    'COND_SAUCE': [
        r'\b(KETCHUP|MAYONNAISE|MAYO|MOUTARDE)\b',
        r'\b(VINAIGRETTE|BEARNAISE|HOLLANDAISE)',
        r'\b(AMORA|HEINZ|BENEDICTA|MAILLE).*(?!VIN)',
        r'\bSAUCE\s+(ALGERIENNE|SAMOURAI|ANDALOUSE|HARISSA)',
    ],
    'COND_EPICE': [
        r'\b(POIVRE|CURRY|PAPRIKA|CUMIN|CANNELLE|MUSCADE)',
        r'\b(THYM|LAURIER|HERBES DE PROVENCE|OREGANO|BASILIC)',
        r'\bEPICE\b',
        r'\b(DUCROS|VERSTEGEN).*EPICE',
    ],
    'COND_BOUILLON': [
        r'\bBOUILLON\s+(DE|CUBE|POUDRE)',
        r'\b(FOND|JUS)\s+(DE VEAU|DE VOLAILLE|DE BOEUF)',
        r'\b(MAGGI|KNORR|LIEBIG).*BOUILLON',
        r'\bCUBE\s+OR\b',
    ],
    'COND_SEL': [
        r'\bSEL\s+(FIN|GROS|FLEUR|GUERANDE)',
    ],
    
    # =========================================================================
    # ÉPICERIE SUCRÉE
    # =========================================================================
    'SUCR_CEREAL': [
        r'\bCEREALE\b',
        r'\b(MUESLI|GRANOLA|CORN.?FLAKES|FLOCONS)',
        r'\b(CHOCAPIC|NESQUIK|SPECIAL.?K|LION|CRUNCH|FITNESS|CHOCO)',
        r'\bKELLOGG',
    ],
    'SUCR_CONF': [
        r'\bCONFITURE\b',
        r'\b(MARMELADE|GELEE)\s+(DE|D\')',
        r'\bMIEL\b(?!.*MIEL AMANDE)',
        r'\b(BONNE MAMAN|ST DALFOUR)',
        r'\bPATE A TARTINER\b',
        r'\bNUTELLA\b',
    ],
    'SUCR_SUCRE': [
        r'\bSUCRE\s+(BLANC|ROUX|CASSONADE|VERGEOISE|GLACE|VANILLE|CRISTAL)',
        r'\bST LOUIS.*SUCRE',
        r'\bEDULCORANT|STEVIA\b',
        r'\bSUCRE\s+\d+KG\b',
    ],
    'SUCR_BISC': [
        r'\bBISCUIT\b',
        r'\b(COOKIE|SABLE|PETIT.?BEURRE|PALMIER|SPECULOOS)',
        r'\b(MADELEINES|GALETTE|GAUFRETTE)',
        r'\b(LU|BN|PRINCE|OREO|GRANOLA)\b(?!.*CEREALE)',
        r'\bGOUTER\b',
    ],
    'SUCR_GATEAU': [
        r'\bGATEAU\b',
        r'\b(CAKE|BROWNIE|MUFFIN|FINANCIER)',
        r'\b(QUATRE.?QUART|MARBR)',
        r'\bTARTE\s+(TATIN|CITRON|POMME)',
    ],
    'SUCR_VIEN': [
        r'\bVIENNOISERIE\b',
        r'\bCROISSANT\b',
        r'\bPAIN\s+(AU CHOCOLAT|AUX RAISINS|CHOCO)',
        r'\b(CHAUSSON|DONUT|BEIGNET|CHOUQUETTE)',
    ],
    'SUCR_CHOCO': [
        r'\bCHOCOLAT\b(?!.*(POUDRE|CHAUD|PAIN))',
        r'\b(TABLETTE|ROCHER|TRUFFE|PRALINE)',
        r'\b(KINDER|FERRERO|LINDT|MILKA|COTE D\'OR)',
        r'\b(MARS|SNICKERS|TWIX|BOUNTY|M&M|MALTESERS)',
        r'\bTOBLERONE\b',
    ],
    'SUCR_BONBON': [
        r'\bBONBON\b',
        r'\b(HARIBO|CARAMBAR|LUTTI|VERQUIN)',
        r'\b(CARAMEL|NOUGAT|DRAGEE|REGLISSE)',
        r'\b(FRAISE|COCA|SCHTROUMPF|TAGADA)',
        r'\bTUBO\b.*\b(MAD|PIK|DRAGIBUS)',
    ],
    'SUCR_FARINE': [
        r'\bFARINE\s+(T\d+|BLE|COMPLETE|FLUIDE)',
        r'\bMAIZENA|FECULE\b',
    ],
    'SUCR_LEVURE': [
        r'\bLEVURE\s+(CHIMIQUE|BOULANGERE|SECHE)',
        r'\bBICARBONATE\b',
    ],
    'SUCR_AROME': [
        r'\bAROME\s+(VANILLE|AMANDE|FLEUR)',
        r'\bEXTRAIT\s+DE\b',
        r'\bVANILUXE|SEBALC\b',
    ],
    'SUCR_NAPPAGE': [
        r'\bNAPPAGE\b',
        r'\b(GLAÇAGE|DECORATION)\s+GATEAU',
        r'\bCHOCOLAT\s+PATISSIER',
    ],
    
    # =========================================================================
    # PRODUITS FRAIS - VIANDES
    # =========================================================================
    'FRAIS_BOEUF': [
        r'\bBOEUF\b',
        r'\b(STEAK|ENTRECOTE|BAVETTE|RUMSTECK|FILET|TOURNEDOS)',
        r'\b(BOURGUIGNON|BROCHETTE|CARPACCIO).*BOEUF',
        r'\bHACHE\s+\d+%',
        r'\bVBF\b',  # Viande Bovine Française
    ],
    'FRAIS_VOLAILLE': [
        r'\b(POULET|DINDE|CANARD|PINTADE)\b',
        r'\b(CUISSE|AILE|FILET|ESCALOPE).*VOLAILLE',
        r'\b(NUGGET|CORDON BLEU|TENDER|WING)',
        r'\bPLT\b.*\b(PANE|SPIC|CRUNCH)',
    ],
    'FRAIS_PORC': [
        r'\bPORC\b',
        r'\b(COTE|ECHINE|FILET MIGNON|TRAVERS)',
        r'\bROTI\s+DE\s+PORC',
    ],
    'FRAIS_AGNEAU': [
        r'\b(AGNEAU|VEAU)\b',
        r'\b(GIGOT|EPAULE|COTELETTE|SOURIS).*AGNEAU',
        r'\b(ESCALOPE|BLANQUETTE).*VEAU',
    ],
    
    # =========================================================================
    # PRODUITS FRAIS - CHARCUTERIE
    # =========================================================================
    'FRAIS_JAMBON': [
        r'\bJAMBON\b',
        r'\b(BLANC|SEC|CRU|FUME|SERRANO|PARME)',
    ],
    'FRAIS_SAUCISSE': [
        r'\bSAUCISSE\b',
        r'\b(MERGUEZ|CHIPOLATA|TOULOUSE|MORTEAU)',
    ],
    'FRAIS_CHARC': [
        r'\b(PATE|RILLETTE|SAUCISSON|TERRINE)\b',
        r'\b(CHORIZO|SALAMI|MORTADELLE|ROSETTE)',
        r'\b(ANDOUILLE|BOUDIN|FOIE GRAS)',
        r'\b(COPPA|BRESAOLA|PANCETTA)',
    ],
    'FRAIS_LARDON': [
        r'\b(LARDON|ALLUMETTE|BACON)\b',
        r'\bPOITRINE\s+(FUMEE|NATURE)',
    ],
    
    # =========================================================================
    # PRODUITS FRAIS - POISSONS
    # =========================================================================
    'FRAIS_POISSON': [
        r'\b(SAUMON|CABILLAUD|COLIN|BAR|DORADE|SOLE|TRUITE)\b',
        r'\b(LIEU|EGLEFIN|MERLU|LOTTE|TURBOT)',
        r'\bPOISSON\s+FRAIS',
        r'\bFILET\s+(DE|D\')\s*(SAUMON|CABILLAUD)',
    ],
    'FRAIS_CRUST': [
        r'\b(CREVETTE|GAMBAS|LANGOUSTINE|HOMARD|CRABE)\b',
        r'\bFRUIT\s+DE\s+MER',
    ],
    'FRAIS_COQUIL': [
        r'\b(MOULE|HUITRE|BULOT|COQUILLE|PALOURDE|PRAIRE)\b',
        r'\bST.?JACQUES\b',
    ],
    
    # =========================================================================
    # PRODUITS FRAIS - AUTRES
    # =========================================================================
    'FRAIS_OEUF': [
        r'\bOEUF\b',
        r'\b\d+\s*(DZ|DOUZAINE)',
        r'\bPLEIN AIR\b',
    ],
    'FRAIS_TRAIT': [
        r'\b(PIZZA|QUICHE|TARTE SALEE)\b(?!.*SURGEL)',
        r'\b(TABOULÉ|SUSHI|WRAP|SANDWICH|PANINI)',
        r'\b(NEMS|SAMOSSA)',
    ],
    
    # =========================================================================
    # SURGELÉS
    # =========================================================================
    'SURG_LEGUME': [
        r'\bSURGEL.*\b(LEGUME|HARICOT|PETIT POIS|EPINARD)',
        r'\b(FRITE|POTATO|POTATOES)\b',
        r'\b(CONGELÉ|SURGELE).*LEGUME',
        r'\bEPINARD.*\bPALET\b',
    ],
    'SURG_VIANDE': [
        r'\bSURGEL.*\b(VIANDE|STEAK|BOULETTE)',
        r'\b(NUGGET|CORDON BLEU).*SURGEL',
    ],
    'SURG_POISSON': [
        r'\bSURGEL.*\bPOISSON',
        r'\bFISH.?STICK\b',
        r'\bPANE.*POISSON',
    ],
    'SURG_PATISS': [
        r'\bSURGEL.*\b(PATISSERIE|TARTE|CROISSANT)',
        r'\bMINI\s+TARTELETTE',
    ],
    'SURG_GLACE': [
        r'\b(GLACE|SORBET|CREME GLACEE)\b',
        r'\b(MAGNUM|CORNETTO|CARTE D\'OR|HAAGEN|BEN.?JERRY)',
        r'\bBAC\s+(GLACE|SORBET)',
    ],
    
    # =========================================================================
    # BOULANGERIE
    # =========================================================================
    'BOUL_PAIN': [
        r'\bPAIN\s+(DE MIE|COMPLET|CEREALE|BURGER|HOT DOG)',
        r'\bBAGUETTE\b',
        r'\b(FOCACCIA|CIABATTA|PANINI)\b(?!.*SURGEL)',
        r'\bTOAST\b',
        r'\bBURGER\s+\d+X',
    ],
    'BOUL_BRIOCHE': [
        r'\bBRIOCHE\b(?!.*PAIN)',
        r'\bBRIOCH\'\b',
    ],
    
    # =========================================================================
    # FRUITS & LÉGUMES
    # =========================================================================
    'FL_FRUIT': [
        r'\b(POMME|POIRE|BANANE|ORANGE|CITRON|MANDARINE)\b(?!.*(JUS|SIROP|CONFITURE))',
        r'\b(FRAISE|FRAMBOISE|CERISE|ABRICOT|PECHE|PRUNE)\b(?!.*(YAOURT|SIROP|CONFITURE))',
        r'\b(RAISIN|MELON|PASTEQUE|ANANAS|MANGUE|KIWI)\b(?!.*(JUS|SIROP))',
        r'\bFRUIT\s+FRAIS',
    ],
    'FL_LEGUME': [
        r'\b(CAROTTE|TOMATE|COURGETTE|AUBERGINE|POIVRON)\b(?!.*(BTE|BOITE|CONSERVE|SAUCE))',
        r'\b(CONCOMBRE|CELERI|POIREAU|CHOU|BROCOLI)\b',
        r'\b(NAVET|RADIS|BETTERAVE|FENOUIL)\b(?!.*BTE)',
        r'\bLEGUME\s+FRAIS',
        r'\bSAL\s+ICEBERG\b',
    ],
    'FL_AROMATE': [
        r'\b(PERSIL|CIBOULETTE|BASILIC|CORIANDRE|MENTHE)\s+FRAIS',
        r'\bAROMATE\s+FRAIS',
    ],
    'FL_SALADE': [
        r'\b(SALADE|LAITUE|ROQUETTE|MACHE|MESCLUN|BATAVIA)\b(?!.*(COMPOS|TRAIT))',
        r'\bSAL\s+ICEBERG\b',
    ],
    
    # =========================================================================
    # PRODUITS DU MONDE
    # =========================================================================
    'MONDE_AFRIQUE': [
        r'\b(ATTIEKE|FOUTOU|GARI|IGNAME|MANIOC|PLANTAIN)',
        r'\b(GOMBO|FEUILLE|PONDU|MOAMBE|NDOLE)',
        r'\b(HUILE ROUGE|HUILE PALME|SOUMBALA|DAWADAWA)',
        r'\bCUBE\s+JUMBO\b',
    ],
    'MONDE_ASIE': [
        r'\b(NOUILLE|RAMEN|SOBA|UDON)\b',
        r'\b(SAUCE SOJA|NUOC MAM|TERIYAKI|SRIRACHA)',
        r'\b(TOFU|MISO|WASABI|GINGEMBRE)\b',
        r'\b(ANJU|ANNAM|BANH)',
    ],
    'MONDE_ORIENT': [
        r'\b(HARISSA|RAS EL HANOUT|ZAATAR|SUMAC)',
        r'\b(LOUKOUM|BAKLAVA|HALAWA|TAHINI)',
        r'\bORIENTAL\b',
    ],
    'MONDE_AMERIQUE': [
        r'\b(TORTILLA|FAJITA|NACHOS|TACO|BURRITO)',
        r'\bTEX.?MEX\b',
        r'\bSALSA\b',
    ],
    'MONDE_HALAL': [
        r'\bHALAL\b',
        r'\bCERT\s+HALAL',
    ],
    
    # =========================================================================
    # SNACKING
    # =========================================================================
    'SNACK_CHIPS': [
        r'\bCHIPS\b',
        r'\b(PRINGLES|LAY\'?S|MONSTER MUNCH|CURLY|BELIN)',
        r'\bCRACKERS\b(?!.*BISCUIT)',
    ],
    'SNACK_FRUIT_SEC': [
        r'\b(CACAHUETE|PISTACHE|NOIX DE CAJOU|AMANDE)\b(?!.*(LAIT|BISCUIT))',
        r'\b(NOISETTE|NOIX)\b(?!.*(COCO|GATEAU))',
        r'\bMIX\s+APERITIF',
        r'\bOLEAGINEUX\b',
    ],
    'SNACK_BISCUIT': [
        r'\b(TUC|BRETZEL|STICK)\s+APERITIF',
        r'\bBISCUIT\s+APERITIF',
    ],
    
    # =========================================================================
    # HYGIÈNE & ENTRETIEN
    # =========================================================================
    'HYG_CORPS': [
        r'\b(SAVON|GEL DOUCHE|SHAMPOO?ING?|DEODORANT)',
        r'\b(DENTIFRICE|BROSSE A DENT)',
        r'\b(DOVE|NIVEA|AXE|HEAD.?SHOULDER|PALMOLIVE)',
    ],
    'HYG_PAPIER': [
        r'\bPAPIER\s+(TOILETTE|WC|HYGIENE)',
        r'\bESSUIE.?TOUT\b',
        r'\bMOUCHOIR\b',
        r'\b(SOPALIN|LOTUS|OKAY|KLEENEX)',
    ],
    'ENTR_LESSIVE': [
        r'\bLESSIVE\b',
        r'\b(ADOUCISSANT|ASSOUPLISSANT)',
        r'\b(ARIEL|SKIP|PERSIL|LE CHAT|DASH|SOUPLINE|LENOR)',
    ],
    'ENTR_NETTOY': [
        r'\b(NETTOYANT|DEGRAISSANT|DETARTRANT|DESINFECTANT)',
        r'\bJAVEL\b',
        r'\b(AJAX|CIF|MR PROPRE|SAINT MARC|DESTOP|CILLIT)',
        r'\bGEL\s+WC\b',
        r'\bACIDE\s+CHLOR',
    ],
    'ENTR_VAISS': [
        r'\bLIQUIDE?\s+VAISS',
        r'\bTABLETTE\s+(LAVE|LV)',
        r'\b(FAIRY|PAIC|CASCADE|FINISH|SUN)\b',
        r'\bLV\s+MAIN\b',
    ],
    
    # =========================================================================
    # CONSOMMABLES PRO
    # =========================================================================
    'PRO_EMBALL': [
        r'\b(BARQUETTE|BARQ)\s+(ALU|PULPE|CARTON)',
        r'\bBTE\s+(BURGER|KEBAB|REPAS|SANDWICH)',
        r'\bPLAT\s+OVAL\s+ALU',
        r'\bSAC\s+(KRAFT|PAPIER|BOUCHER)',
    ],
    'PRO_JETABLE': [
        r'\bGOB(ELET)?\s+(CARTON|PLASTIQUE|KRAFT)',
        r'\bSERV(IETTE)?\s+\d+\s*PLI',
        r'\bNAPPE\s+(EXTRA|PAPIER)',
        r'\bSET\s+DE\s+TABLE',
        r'\bCOUV(ERT)?\s+(PLASTIQUE|BOIS)',
        r'\bASSIETTE\s+CARTON',
    ],
    'PRO_FILM': [
        r'\bFILM\s+(ALIMENTAIRE|ETIRABLE)',
        r'\bPAPIER\s+(ALU|CUISSON|SULFURISE)',
        r'\bALU\s+\d+',
        r'\bBOBINE\b',
    ],
    'PRO_PROTECT': [
        r'\bCHARLOTTE\b',
        r'\bGANT\s+(JETABLE|VINYL|LATEX|NITRILE)',
        r'\bMASQUE\s+(3 PLIS|JETABLE|CHIRURGICAL)',
    ],
    'PRO_ETIQ': [
        r'\bETIQUETTE\s+(TRACABILITE|ALIMENTAIRE)',
    ],
}

def classify_product(product_name: str) -> Tuple[str, str]:
    """
    Classifie un produit dans une catégorie.
    Retourne (code_categorie, pattern_match)
    """
    product_name = product_name.upper()
    
    for category, patterns in CLASSIFICATION_RULES.items():
        for pattern in patterns:
            if re.search(pattern, product_name, re.IGNORECASE):
                return (category, pattern)
    
    return ('AUTRE', None)


def classify_all_products(products: List[Dict]) -> Dict[str, List]:
    """
    Classifie tous les produits et retourne les statistiques.
    """
    results = defaultdict(list)
    
    for p in products:
        category, pattern = classify_product(p['nom'])
        results[category].append({
            'id': p['id'],
            'nom': p['nom'],
            'pattern': pattern
        })
    
    return dict(results)


def generate_sql_updates(results: Dict[str, List]) -> str:
    """
    Génère le SQL pour mettre à jour les catégories des produits.
    """
    sql_lines = [
        "-- Script de mise à jour des catégories produits",
        "-- Généré automatiquement",
        "",
        "BEGIN;",
        ""
    ]
    
    for category, products in results.items():
        if category == 'AUTRE':
            continue
            
        ids = [str(p['id']) for p in products]
        if ids:
            sql_lines.append(f"-- {category}: {len(ids)} produits")
            
            # Batch par 100 pour éviter les requêtes trop longues
            for i in range(0, len(ids), 100):
                batch = ids[i:i+100]
                sql_lines.append(
                    f"UPDATE public.produits SET categorie = '{category}' "
                    f"WHERE id IN ({', '.join(batch)});"
                )
            sql_lines.append("")
    
    sql_lines.append("COMMIT;")
    
    return '\n'.join(sql_lines)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    # Charger les produits
    products = []
    in_copy = False
    
    with open('/mnt/user-data/uploads/epicerie_backup_20251030_141910_2000-articles.sql', 'r', encoding='utf-8') as f:
        for line in f:
            if 'COPY public.produits ' in line and 'FROM stdin' in line:
                in_copy = True
                continue
            if in_copy:
                if line.startswith('\\'):
                    break
                parts = line.strip().split('\t')
                if len(parts) >= 5:
                    products.append({
                        'id': parts[0],
                        'nom': parts[1],
                    })
    
    print(f"Total produits à classifier: {len(products)}")
    print("="*80)
    
    # Classifier
    results = classify_all_products(products)
    
    # Statistiques
    print("\nRÉSULTATS DE CLASSIFICATION\n")
    
    total_classifies = 0
    for cat in sorted(results.keys()):
        count = len(results[cat])
        if cat != 'AUTRE':
            total_classifies += count
        print(f"  {cat}: {count} produits")
    
    non_classes = len(results.get('AUTRE', []))
    print(f"\n{'='*80}")
    print(f"RÉSUMÉ:")
    print(f"  - Classifiés automatiquement: {total_classifies} ({total_classifies*100/len(products):.1f}%)")
    print(f"  - Non classés (AUTRE): {non_classes} ({non_classes*100/len(products):.1f}%)")
    print(f"{'='*80}")
    
    # Générer le SQL
    sql = generate_sql_updates(results)
    with open('/home/claude/update_categories.sql', 'w') as f:
        f.write(sql)
    print(f"\nScript SQL généré: /home/claude/update_categories.sql")
    
    # Afficher quelques non-classés pour review
    print("\n" + "="*80)
    print("EXEMPLES DE PRODUITS NON CLASSÉS (à revoir manuellement):")
    print("="*80)
    autres = results.get('AUTRE', [])
    for p in sorted(autres, key=lambda x: x['nom'])[:50]:
        print(f"  - {p['nom'][:70]}")
