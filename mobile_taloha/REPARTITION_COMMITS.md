# Répartition des commits — module `mobile`

Projet TPI RC Camera · 3 développeurs · ordre de merge recommandé : **Johary → Dev A → Dev B**

---

## Vue d'ensemble

| Rôle | Responsabilité |
|------|----------------|
| **Johary** | Création du projet Android, thème, layout principal, flux caméra MJPEG |
| **Dev A** | Modèle de direction, API réseau press/release, logique ViewModel direction |
| **Dev B** | Panneaux de contrôle UI (virage / vitesse), lifecycle activité |

```
Commit 1 (Johary)          Commit 2 (Dev A)           Commit 3 (Dev B)
──────────────          ────────────────           ────────────────
Projet Gradle           Direction enum             ControlPanel UI
Manifest + réseau       DirectionRepository        DirectionButton
Thème Compose           ViewModel direction        Direction.toIcon()
CameraRepository        URLs /control/*            MainActivity.onPause
MjpegStreamReader
ViewModel caméra
Layout + zone caméra
```

---

## Commit 1 — Johary

**Message suggéré :**
```
feat(mobile): init projet Android, layout de base et récupération flux caméra MJPEG
```

### Fichiers à créer (fichier entier)

| Fichier | Lignes | Description |
|---------|--------|-------------|
| `settings.gradle.kts` | 1–24 | Configuration Gradle, nom du projet |
| `build.gradle.kts` | 1–5 | Plugins racine (Android + Compose) |
| `gradle.properties` | fichier entier | Propriétés Gradle du projet |
| `gradle/wrapper/gradle-wrapper.properties` | fichier entier | Version Gradle wrapper |
| `app/build.gradle.kts` | 1–76 | Module app : SDK, BuildConfig IP/port, dépendances OkHttp + Compose |
| `app/src/main/AndroidManifest.xml` | 1–34 | Permissions INTERNET, activité landscape, cleartext HTTP |
| `app/src/main/res/xml/network_security_config.xml` | 1–5 | Autorisation HTTP vers le Raspberry Pi |
| `app/src/main/res/values/strings.xml` | fichier entier | Nom de l'application |
| `app/src/main/res/values/themes.xml` | fichier entier | Thème XML de base |
| `app/src/main/res/values/colors.xml` | fichier entier | Couleurs ressources |
| `app/src/main/java/com/tpi/mobile/ui/theme/Color.kt` | 1–11 | Palette Material de base |
| `app/src/main/java/com/tpi/mobile/ui/theme/Type.kt` | 1–34 | Typographie Material |
| `app/src/main/java/com/tpi/mobile/ui/theme/Theme.kt` | 1–58 | `MobileTheme` Compose |
| `app/src/main/java/com/tpi/mobile/camera/CameraRepository.kt` | 1–44 | GET `/status` + délégation flux `/video` |
| `app/src/main/java/com/tpi/mobile/camera/MjpegStreamReader.kt` | 1–198 | Parser multipart MJPEG frame par frame |

### Fichiers partiels (plages de lignes)

#### `app/src/main/java/com/tpi/mobile/MainActivity.kt`

| Lignes | Contenu |
|--------|---------|
| **1–21** | Activity Compose, `viewModels()`, `setContent { RcCameraScreen }` |

> Ne pas inclure `onPause()` (lignes 23–30) — réservé à Dev B.

---

#### `app/src/main/java/com/tpi/mobile/camera/CameraState.kt`

| Lignes | Contenu |
|--------|---------|
| **17–22** | `CameraConnectionConfig` : `host`, `port`, `videoUrl`, `statusUrl` |
| **27–57** | `CameraUiState` (Idle / Connecting / Streaming / Error) + `CameraStatus` |

> Ne pas inclure l'enum `Direction` (lignes 9–15) ni les URLs `controlPressUrl` / `controlReleaseUrl` (lignes 23–24) — réservés à Dev A.

---

#### `app/src/main/java/com/tpi/mobile/camera/CameraViewModel.kt`

| Lignes | Contenu |
|--------|---------|
| **1–16** | Imports, déclaration classe, `cameraRepository`, `streamJob` |
| **21–38** | `_cameraState`, `_host`, `_port` + StateFlows |
| **40–94** | `updateHost`, `updatePort`, `connect`, `disconnect`, `retryAfterError` |
| **131–141** | `buildConfig()` helper privé |

> Ne pas inclure `directionRepository` (l. 18), `_activeDirections` (l. 28–30), ni `pressDirection` / `releaseDirection` (l. 96–122) — réservés à Dev A.  
> Ne pas inclure `onCleared()` (l. 124–129) — réservé à Dev B.

---

#### `app/src/main/java/com/tpi/mobile/ui/CameraScreen.kt`

| Lignes | Contenu |
|--------|---------|
| **1–91** | Imports + design tokens (`ScreenBg`, `AccentBlue`, etc.) |
| **95–167** | `RcCameraScreen` : layout `Row` 3 colonnes (panneaux + centre caméra) |
| **284–347** | `ConnectionTextField` |
| **349–436** | `ConnectionBar` (IP, port, bouton Connecter/Stop, indicateur statut) |
| **438–460** | `CameraViewBox` (switch selon `CameraUiState`) |
| **462–511** | `CameraOffOverlay` |
| **513–524** | `ConnectingOverlay` |
| **526–561** | `ErrorOverlay` |
| **563–585** | `StreamingView` (décodage JPEG → `ImageBitmap`) |
| **587–619** | `StreamInfoOverlay` (résolution + fps) |

> Ne pas inclure `ControlPanel` / `DirectionButton` (l. 169–282) ni `Direction.toIcon()` (l. 621–629) — réservés à Dev B.

**Note layout (l. 113–124 et 152–163) :** appeler `ControlPanel(...)` avec des stubs vides ou des `Box` placeholder en attendant le commit de Dev B.

---

## Commit 2 — Dev A

**Message suggéré :**
```
feat(mobile): commandes direction press/release vers le Raspberry Pi
```

**Prérequis :** merge du commit 1 (Johary).

### Fichiers à créer (fichier entier)

| Fichier | Lignes | Description |
|---------|--------|-------------|
| `app/src/main/java/com/tpi/mobile/camera/DirectionRepository.kt` | 1–42 | GET `/control/press/{cmd}` et `/control/release/{cmd}` via OkHttp |

### Fichiers partiels (plages de lignes)

#### `app/src/main/java/com/tpi/mobile/camera/CameraState.kt`

| Lignes | Contenu |
|--------|---------|
| **9–15** | `enum class Direction` (FORWARD, BACKWARD, LEFT, RIGHT, STOP) |
| **23–24** | `controlPressUrl()` et `controlReleaseUrl()` dans `CameraConnectionConfig` |

---

#### `app/src/main/java/com/tpi/mobile/camera/CameraViewModel.kt`

| Lignes | Contenu |
|--------|---------|
| **18** | `private val directionRepository = DirectionRepository()` |
| **28–30** | `_activeDirections` + `activeDirections` StateFlow |
| **96–122** | `pressDirection()` et `releaseDirection()` |

---

## Commit 3 — Dev B

**Message suggéré :**
```
feat(mobile): panneaux de contrôle direction et lifecycle connexion caméra
```

**Prérequis :** merge des commits 1 (Johary) et 2 (Dev A).

### Fichiers partiels (plages de lignes)

#### `app/src/main/java/com/tpi/mobile/MainActivity.kt`

| Lignes | Contenu |
|--------|---------|
| **23–30** | `onPause()` → `cameraViewModel.disconnect()` pour libérer le flux réseau |

---

#### `app/src/main/java/com/tpi/mobile/camera/CameraViewModel.kt`

| Lignes | Contenu |
|--------|---------|
| **124–129** | `onCleared()` → `disconnect()` avant destruction du ViewModel |

---

#### `app/src/main/java/com/tpi/mobile/ui/CameraScreen.kt`

| Lignes | Contenu |
|--------|---------|
| **169–217** | `ControlPanel` : panneau latéral (titre + 2 boutons direction) |
| **219–282** | `DirectionButton` : press-and-hold avec animation scale/couleur |
| **621–629** | Extension `Direction.toIcon()` → icônes Material (flèches) |

**Remplacer** les placeholders du commit 1 par les vrais appels `ControlPanel` déjà présents dans `RcCameraScreen` (l. 114–124 et 153–163).

---

## Récapitulatif par fichier

| Fichier | Johary | Dev A | Dev B |
|---------|-----|-------|-------|
| `settings.gradle.kts` | ✅ entier | | |
| `build.gradle.kts` | ✅ entier | | |
| `app/build.gradle.kts` | ✅ entier | | |
| `AndroidManifest.xml` | ✅ entier | | |
| `network_security_config.xml` | ✅ entier | | |
| `ui/theme/*.kt` | ✅ entier | | |
| `CameraRepository.kt` | ✅ entier | | |
| `MjpegStreamReader.kt` | ✅ entier | | |
| `DirectionRepository.kt` | | ✅ entier | |
| `CameraState.kt` | l. 17–22, 27–57 | l. 9–15, 23–24 | |
| `CameraViewModel.kt` | l. 1–16, 21–38, 40–94, 131–141 | l. 18, 28–30, 96–122 | l. 124–129 |
| `MainActivity.kt` | l. 1–21 | | l. 23–30 |
| `CameraScreen.kt` | l. 1–91, 95–167, 284–619 | | l. 169–282, 621–629 |

---

## Workflow Git recommandé

```bash
# Johary — branche initiale
git checkout -b feat/mobile-camera-base
# ... commits des fichiers ci-dessus ...
git push -u origin feat/mobile-camera-base
# → ouvrir PR / merger sur main

# Dev A — après merge de Johary
git checkout main && git pull
git checkout -b feat/mobile-direction-api
# ... commits Dev A ...
git push -u origin feat/mobile-direction-api

# Dev B — après merge de Dev A
git checkout main && git pull
git checkout -b feat/mobile-control-panels
# ... commits Dev B ...
git push -u origin feat/mobile-control-panels
```

---

## Vérification finale (tous)

Après les 3 commits mergés, l'app doit :

1. Afficher le layout paysage 3 colonnes (Virage | Caméra | Vitesse)
2. Se connecter au flux MJPEG `http://<IP>:5000/video`
3. Afficher résolution et fps en overlay
4. Envoyer press/release sur `/control/press/{cmd}` et `/control/release/{cmd}`
5. Couper le flux automatiquement en `onPause`

**Test rapide :**
```bash
cd mobile
./gradlew assembleDebug
```
