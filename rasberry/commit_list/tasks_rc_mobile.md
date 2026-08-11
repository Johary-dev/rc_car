# Répartition des tâches — Mise à niveau de `rc-mobile` vers `RcCamera`

**Objectif :** Amener le projet `rc-mobile` au même niveau de fonctionnalités que le projet de référence `RcCamera`.

**Projet source (à modifier) :**
`D:\LESONA\M2\TPI\tpi-itu-25-26-tantely_johary_aldo_haroavo_iaritina\rc-mobile\`

**Projet de référence :**
`D:\LESONA\M2\TPI\projet_taloha\projet\Kotlin\`

---

## Résumé des fonctionnalités manquantes

| # | Fonctionnalité | Fichiers impactés |
|---|---------------|-------------------|
| 1 | Fix bug package + enrichissement `CameraState` | `DirectionRepository.kt`, `CameraViewModel.kt`, `CameraState.kt` |
| 2 | `CameraRepository` : ping chronométré + commande autopilote | `CameraRepository.kt` |
| 3 | `DirectionRepository` : commande throttle | `DirectionRepository.kt` |
| 4 | `CameraViewModel` : autopilote + StateFlows manquants | `CameraViewModel.kt` |
| 5 | `CameraViewModel` : throttle + ping périodique | `CameraViewModel.kt` |
| 6 | `CameraScreen` : nouveaux composables UI | `CameraScreen.kt` |

---

## Graphe de dépendances entre commits

```
VAGUE 1 — aucune dépendance (Johary seul, à faire EN PREMIER)
─────────────────────────────────────────────────────────────
  C1 (fix package)
  C2 (switchUrl / throttleUrl dans CameraState)
  C3 (NoCamera + battery dans CameraState)

VAGUE 2 — dépend de la vague 1 (Aldo + Haroavo en parallèle)
─────────────────────────────────────────────────────────────
  C4 (fetchStatusTimed)       ← nécessite C3
  C5 (sendSwitch)             ← nécessite C2
  C6 (sendThrottle)           ← nécessite C1 + C2

VAGUE 3 — dépend de la vague 2 (Haroavo + Tantely + début Iaritina)
─────────────────────────────────────────────────────────────
  C7  (toggleAutopilot VM)    ← nécessite C5
  C8  (setThrottle VM)        ← nécessite C6
  C9  (startPinging VM)       ← nécessite C4
  C12 (NoCameraOverlay)       ← nécessite C3  ← Iaritina peut commencer ici

VAGUE 4 — dépend de la vague 3 (Iaritina)
─────────────────────────────────────────────────────────────
  C10 (AutopilotBar)          ← nécessite C7
  C11 (ThrottleSlider + SignalBars + BatteryGauge) ← nécessite C8 + C9

VAGUE 5 — tout le reste est mergé (Iaritina, dernier commit)
─────────────────────────────────────────────────────────────
  C13 (SignalBars + BatteryGauge dans ConnectionBar) ← nécessite C9 + C11
```

### Chaînes de dépendances critiques (chemin le plus long)

```
C3 → C4 → C9 → C11 → C13
C2 → C5 → C7 → C10
C1 + C2 → C6 → C8 → C11 → C13
```

---

## Tableau d'ordre d'envoi des commits (qui attend qui)

| Commit | Auteur | Peut commencer quand ? | Débloque |
|--------|--------|------------------------|----------|
| **C1** | Johary | Immédiatement | C6 |
| **C2** | Johary | Immédiatement | C5, C6 |
| **C3** | Johary | Immédiatement | C4, C12 |
| **C4** | Aldo | Après merge de **C3** | C9 |
| **C5** | Aldo | Après merge de **C2** | C7 |
| **C6** | Haroavo | Après merge de **C1** + **C2** | C8 |
| **C7** | Haroavo | Après merge de **C5** | C10 |
| **C8** | Tantely | Après merge de **C6** | C11 |
| **C9** | Tantely | Après merge de **C4** | C11, C13 |
| **C10** | Iaritina | Après merge de **C7** | — |
| **C11** | Iaritina | Après merge de **C8** + **C9** | C13 |
| **C12** | Iaritina | Après merge de **C3** | — |
| **C13** | Iaritina | Après merge de **C9** + **C11** | — |

> **Remarque :** C12 est indépendant de C10, C11 et C13 — Iaritina peut le faire
> dès que C3 est mergé, sans attendre les autres commits de la vague 4.

---

## DEV 1 — Johary : Fix package + enrichissement de `CameraState.kt`

### Commit 1 — `fix: correct wrong package in DirectionRepository`
> **Prérequis :** aucun — premier commit à envoyer
> **Débloque :** C6 (Haroavo ne peut pas commencer `sendThrottle` avant ce fix)

**Fichier :** `app/src/main/java/com/tpi/rc_mobile/camera/DirectionRepository.kt`

| Ligne | Action | Avant | Après |
|-------|--------|-------|-------|
| 1 | Modifier la déclaration du package | `package com.tpi.mobile.camera` | `package com.tpi.rc_mobile.camera` |
| 3–4 | Supprimer les imports explicites qui compensaient le mauvais package | `import com.tpi.rc_mobile.camera.CameraConnectionConfig` et `import com.tpi.rc_mobile.camera.Direction` | *(supprimer ces deux lignes — ils sont maintenant dans le même package)* |

**Fichier :** `app/src/main/java/com/tpi/rc_mobile/camera/CameraViewModel.kt`

| Ligne | Action | Avant | Après |
|-------|--------|-------|-------|
| 4 | Corriger l'import de `DirectionRepository` | `import com.tpi.mobile.camera.DirectionRepository` | `import com.tpi.rc_mobile.camera.DirectionRepository` |

---

### Commit 2 — `feat(state): add switchAutoUrl, switchManualUrl, controlThrottleUrl to CameraConnectionConfig`
> **Prérequis :** aucun — peut être fait en même temps que C1 et C3
> **Débloque :** C5 (Aldo) + C6 (Haroavo)

**Fichier :** `app/src/main/java/com/tpi/rc_mobile/camera/CameraState.kt`

| Ligne | Action | Code à ajouter |
|-------|--------|----------------|
| Après ligne 19 (après `controlReleaseUrl`) | Ajouter 3 nouvelles fonctions dans `CameraConnectionConfig` | Voir bloc ci-dessous |

```kotlin
    fun switchAutoUrl()   = "http://$host:$port/switch/auto"
    fun switchManualUrl() = "http://$host:$port/switch/manual"
    fun controlThrottleUrl(percent: Int) = "http://$host:$port/control/throttle/$percent"
```

---

### Commit 3 — `feat(state): add NoCamera state and battery field to CameraStatus`
> **Prérequis :** aucun — peut être fait en même temps que C1 et C2
> **Débloque :** C4 (Aldo) + C12 (Iaritina)

**Fichier :** `app/src/main/java/com/tpi/rc_mobile/camera/CameraState.kt`

**Modification 1 :** ajouter l'état `NoCamera` dans `CameraUiState` (ligne 27, après `Connecting`)

```kotlin
    /** Raspberry Pi connecté mais caméra physiquement absente. */
    data object NoCamera : CameraUiState
```

**Modification 2 :** enrichir `CameraStatus` (ligne 48–52) — ajouter le champ `battery`

```kotlin
data class CameraStatus(
    val resolution: String?,
    val fps: Int?,
    val jpegQuality: Int?,
    val battery: Int?,           // pourcentage batterie, null si absent
)
```

---

## DEV 2 — Aldo : Enrichissement de `CameraRepository.kt`

### Commit 4 — `feat(repo): add fetchStatusTimed for latency measurement`
> **Prérequis :** attendre le merge de **C3** (le champ `battery` doit exister dans `CameraStatus`)
> **Débloque :** C9 (Tantely)

**Fichier :** `app/src/main/java/com/tpi/rc_mobile/camera/CameraRepository.kt`

**Ajouter un second client OkHttp dédié au ping** (après ligne 16, à l'intérieur de la classe) :

```kotlin
    /** Client dédié aux pings périodiques — timeout court pour ne pas bloquer l'UI. */
    private val pingClient: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(2, TimeUnit.SECONDS)
        .readTimeout(2, TimeUnit.SECONDS)
        .build()
```

**Modifier `fetchStatus` (lignes 18–36) pour parser aussi le champ `battery` :**

```kotlin
    suspend fun fetchStatus(config: CameraConnectionConfig): CameraStatus =
        withContext(Dispatchers.IO) {
            val request = Request.Builder().url(config.statusUrl).get().build()

            httpClient.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    throw IOException("Statut indisponible (HTTP ${response.code})")
                }

                val body = response.body?.string().orEmpty()
                val json = JSONObject(body)

                CameraStatus(
                    resolution   = json.optString("resolution").ifBlank { null },
                    fps          = json.optInt("fps", -1).takeIf { it >= 0 },
                    jpegQuality  = json.optInt("jpeg_quality", -1).takeIf { it >= 0 },
                    battery      = json.optInt("battery", -1).takeIf { it >= 0 },
                )
            }
        }
```

**Ajouter `fetchStatusTimed` après la fin de `stream` (après ligne 43) :**

```kotlin
    /**
     * Récupère le statut ET mesure la latence aller-retour en ms.
     * Retourne null si la requête échoue (pas bloquant).
     */
    suspend fun fetchStatusTimed(config: CameraConnectionConfig): Pair<CameraStatus, Long>? =
        withContext(Dispatchers.IO) {
            try {
                val request = Request.Builder().url(config.statusUrl).get().build()
                val start = System.currentTimeMillis()

                pingClient.newCall(request).execute().use { response ->
                    val elapsed = System.currentTimeMillis() - start
                    if (!response.isSuccessful) return@withContext null

                    val body = response.body?.string().orEmpty()
                    val json = JSONObject(body)

                    val status = CameraStatus(
                        resolution  = json.optString("resolution").ifBlank { null },
                        fps         = json.optInt("fps", -1).takeIf { it >= 0 },
                        jpegQuality = json.optInt("jpeg_quality", -1).takeIf { it >= 0 },
                        battery     = json.optInt("battery", -1).takeIf { it >= 0 },
                    )
                    Pair(status, elapsed)
                }
            } catch (_: Exception) {
                null
            }
        }
```

---

### Commit 5 — `feat(repo): add sendSwitch for autopilot on/off`
> **Prérequis :** attendre le merge de **C2** (`switchAutoUrl`/`switchManualUrl` doivent exister)
> **Débloque :** C7 (Haroavo)

**Fichier :** `app/src/main/java/com/tpi/rc_mobile/camera/CameraRepository.kt`

**Ajouter après `fetchStatusTimed` :**

```kotlin
    /**
     * Bascule le mode autopilote du Raspberry Pi.
     * [auto] = true → /switch/auto, false → /switch/manual
     */
    suspend fun sendSwitch(config: CameraConnectionConfig, auto: Boolean) {
        withContext(Dispatchers.IO) {
            try {
                val url = if (auto) config.switchAutoUrl() else config.switchManualUrl()
                val request = Request.Builder().url(url).get().build()
                httpClient.newCall(request).execute().close()
            } catch (_: Exception) { /* non bloquant */ }
        }
    }
```

---

## DEV 3 — Haroavo : `DirectionRepository` throttle + `CameraViewModel` autopilote

### Commit 6 — `feat(repo): add sendThrottle to DirectionRepository`
> **Prérequis :** attendre le merge de **C1** (package corrigé) + **C2** (`controlThrottleUrl` doit exister)
> **Débloque :** C8 (Tantely)

**Fichier :** `app/src/main/java/com/tpi/rc_mobile/camera/DirectionRepository.kt`

**Ajouter après `sendRelease` (ligne 32) :**

```kotlin
    /**
     * Envoie une valeur de vitesse entre -100 et 100.
     * Convertit le Float [-1.0 … 1.0] en entier pour l'URL.
     */
    suspend fun sendThrottle(config: CameraConnectionConfig, value: Float) {
        val percent = (value * 100).toInt().coerceIn(-100, 100)
        send(config.controlThrottleUrl(percent))
    }
```

---

### Commit 7 — `feat(vm): add autopilot toggle with StateFlow`
> **Prérequis :** attendre le merge de **C5** (`cameraRepository.sendSwitch` doit exister)
> **Débloque :** C10 (Iaritina)

**Fichier :** `app/src/main/java/com/tpi/rc_mobile/camera/CameraViewModel.kt`

**Ajouter les imports manquants** (section imports, après ligne 13) :

```kotlin
import kotlinx.coroutines.delay
```

**Ajouter le StateFlow `autopilotActive`** (après ligne 28, bloc "Direction state") :

```kotlin
    // --- Autopilote state ---------------------------------------------------

    private val _autopilotActive = MutableStateFlow(false)
    val autopilotActive: StateFlow<Boolean> = _autopilotActive.asStateFlow()
```

**Ajouter la fonction `toggleAutopilot`** (après `releaseDirection`, avant `onCleared`) :

```kotlin
    fun toggleAutopilot() {
        val newState = !_autopilotActive.value
        _autopilotActive.value = newState
        val config = buildConfig() ?: return
        viewModelScope.launch {
            cameraRepository.sendSwitch(config, newState)
        }
    }
```

---

## DEV 4 — Tantely : `CameraViewModel` — throttle + ping périodique

### Commit 8 — `feat(vm): add throttle StateFlow and setThrottle/releaseThrottle`
> **Prérequis :** attendre le merge de **C6** (`directionRepository.sendThrottle` doit exister)
> **Débloque :** C11 (Iaritina — en attente aussi de C9)

**Fichier :** `app/src/main/java/com/tpi/rc_mobile/camera/CameraViewModel.kt`

**Ajouter le StateFlow `throttleValue`** (après le bloc autopilotActive du commit 7) :

```kotlin
    // --- Throttle state -----------------------------------------------------

    private val _throttleValue = MutableStateFlow(0f)
    val throttleValue: StateFlow<Float> = _throttleValue.asStateFlow()
```

**Ajouter les fonctions throttle** (après `toggleAutopilot`) :

```kotlin
    fun setThrottle(value: Float) {
        val clamped = value.coerceIn(-1f, 1f)
        _throttleValue.value = clamped
        val config = buildConfig() ?: return
        viewModelScope.launch {
            directionRepository.sendThrottle(config, clamped)
        }
    }

    fun releaseThrottle() {
        _throttleValue.value = 0f
        val config = buildConfig() ?: return
        viewModelScope.launch {
            directionRepository.sendThrottle(config, 0f)
        }
    }
```

---

### Commit 9 — `feat(vm): add periodic ping with latencyMs and batteryPercent StateFlows`
> **Prérequis :** attendre le merge de **C4** (`cameraRepository.fetchStatusTimed` doit exister)
> **Débloque :** C11 (en attente aussi de C8) + C13 (Iaritina)

**Fichier :** `app/src/main/java/com/tpi/rc_mobile/camera/CameraViewModel.kt`

**Ajouter les imports manquants** (si non présents) :

```kotlin
import kotlinx.coroutines.isActive
import kotlin.math.roundToInt
```

**Ajouter les StateFlows latence et batterie** (après le bloc throttle) :

```kotlin
    // --- Ping / batterie state ----------------------------------------------

    private val _latencyMs      = MutableStateFlow<Long?>(null)
    val latencyMs: StateFlow<Long?> = _latencyMs.asStateFlow()

    private val _batteryPercent = MutableStateFlow<Int?>(null)
    val batteryPercent: StateFlow<Int?> = _batteryPercent.asStateFlow()

    private var pingJob: Job? = null
```

**Ajouter les fonctions `startPinging` / `stopPinging`** (avant `onCleared`) :

```kotlin
    private fun startPinging(config: CameraConnectionConfig) {
        stopPinging()
        pingJob = viewModelScope.launch {
            while (isActive) {
                val result = cameraRepository.fetchStatusTimed(config)
                if (result != null) {
                    val (status, latency) = result
                    _latencyMs.value      = latency
                    _batteryPercent.value = status.battery
                }
                delay(3_000L)
            }
        }
    }

    private fun stopPinging() {
        pingJob?.cancel()
        pingJob = null
        _latencyMs.value      = null
        _batteryPercent.value = null
    }
```

**Modifier `connect()`** — appeler `startPinging` après avoir obtenu le statut initial (après ligne 59, l'appel à `cameraRepository.fetchStatus`) :

```kotlin
        // Dans streamJob = viewModelScope.launch { ... }
        // Après : val status = runCatching { ... }.getOrNull()
        // Ajouter :
                startPinging(config)
```

**Modifier `disconnect()`** — ajouter `stopPinging()` avant `streamJob?.cancel()` :

```kotlin
    fun disconnect() {
        stopPinging()
        streamJob?.cancel()
        streamJob = null
        _cameraState.value = CameraUiState.Idle
    }
```

**Modifier `onCleared()`** :

```kotlin
    override fun onCleared() {
        stopPinging()
        disconnect()
        super.onCleared()
    }
```

---

## DEV 5 — Iaritina : Nouveaux composables dans `CameraScreen.kt`

### Commit 10 — `feat(ui): add AutopilotBar composable`
> **Prérequis :** attendre le merge de **C7** (`autopilotActive` StateFlow + `toggleAutopilot` dans le ViewModel)
> **Débloque :** rien — commit terminal pour cette branche

**Fichier :** `app/src/main/java/com/tpi/rc_mobile/ui/CameraScreen.kt`

**Ajouter les imports manquants** (après les imports existants, avant ligne 77) :

```kotlin
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.material.icons.filled.AccountBox
import androidx.compose.ui.input.pointer.pointerInput
```

**Collecter les nouveaux StateFlows dans `RcCameraScreen`** — modifier les lignes 96–99 :

```kotlin
    val cameraState       by viewModel.cameraState.collectAsStateWithLifecycle()
    val activeDirections  by viewModel.activeDirections.collectAsStateWithLifecycle()
    val autopilotActive   by viewModel.autopilotActive.collectAsStateWithLifecycle()
    val throttleValue     by viewModel.throttleValue.collectAsStateWithLifecycle()
    val latencyMs         by viewModel.latencyMs.collectAsStateWithLifecycle()
    val batteryPercent    by viewModel.batteryPercent.collectAsStateWithLifecycle()
    val host              by viewModel.host.collectAsStateWithLifecycle()
    val port              by viewModel.port.collectAsStateWithLifecycle()
```

**Ajouter `AutopilotBar`** dans le `Column` central de `RcCameraScreen` (après `ConnectionBar`, avant `CameraViewBox`) :

```kotlin
                    AutopilotBar(
                        autopilotActive  = autopilotActive,
                        onToggle         = viewModel::toggleAutopilot,
                    )
```

**Ajouter le composable `AutopilotBar`** (après la fin de `ControlPanel`, avant `DirectionButton`) :

```kotlin
@Composable
private fun AutopilotBar(
    autopilotActive: Boolean,
    onToggle: () -> Unit,
) {
    val bg by animateColorAsState(
        targetValue = if (autopilotActive) Color(0xFF0D2550) else PanelBg,
        label = "autopilot_bg",
    )
    val border by animateColorAsState(
        targetValue = if (autopilotActive) AccentBlue else ButtonBorder,
        label = "autopilot_border",
    )

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(10.dp))
            .background(bg)
            .border(1.dp, border, RoundedCornerShape(10.dp))
            .pointerInput(Unit) { detectTapGestures(onTap = { onToggle() }) }
            .padding(horizontal = 14.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(
            text = "Autopilote",
            color = if (autopilotActive) AccentBlue else TextSecondary,
            fontSize = 12.sp,
            fontWeight = FontWeight.Medium,
        )
        Text(
            text = if (autopilotActive) "ON" else "OFF",
            color = if (autopilotActive) AccentBlue else TextSecondary,
            fontSize = 12.sp,
            fontWeight = FontWeight.Bold,
        )
    }
}
```

---

### Commit 11 — `feat(ui): add ThrottleSlider, SignalBars, BatteryGauge composables`
> **Prérequis :** attendre le merge de **C8** (`throttleValue`, `setThrottle`, `releaseThrottle`) + **C9** (`latencyMs`, `batteryPercent`)
> **Débloque :** C13

**Fichier :** `app/src/main/java/com/tpi/rc_mobile/ui/CameraScreen.kt`

**Remplacer le panneau droit** (lignes 150–161 — `ControlPanel` "Vitesse") par un `ThrottleSlider` dans `RcCameraScreen` :

```kotlin
                // ── Panneau droit : Throttle (glisser vertical) ──────────────
                ThrottleSlider(
                    modifier = Modifier
                        .width(110.dp)
                        .fillMaxHeight(),
                    throttleValue  = throttleValue,
                    onThrottle     = viewModel::setThrottle,
                    onRelease      = viewModel::releaseThrottle,
                )
```

**Ajouter le composable `ThrottleSlider`** (après `AutopilotBar`) :

```kotlin
@Composable
private fun ThrottleSlider(
    modifier: Modifier,
    throttleValue: Float,
    onThrottle: (Float) -> Unit,
    onRelease: () -> Unit,
) {
    val trackHeight = remember { mutableStateOf(0f) }
    val fillFraction = ((throttleValue + 1f) / 2f).coerceIn(0f, 1f)

    Box(
        modifier = modifier
            .clip(RoundedCornerShape(16.dp))
            .background(PanelBg)
            .padding(6.dp)
            .pointerInput(Unit) {
                detectVerticalDragGestures(
                    onDragEnd = { onRelease() },
                    onVerticalDrag = { _, dragAmount ->
                        if (trackHeight.value > 0f) {
                            val delta = -(dragAmount / trackHeight.value) * 2f
                            onThrottle((throttleValue + delta).coerceIn(-1f, 1f))
                        }
                    },
                )
            },
        contentAlignment = Alignment.Center,
    ) {
        Column(
            modifier = Modifier.fillMaxSize(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Text("Throttle", color = TextSecondary, fontSize = 10.sp, fontWeight = FontWeight.Medium, letterSpacing = 1.sp)
            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(10.dp))
                    .background(ButtonBg)
                    .border(1.dp, ButtonBorder, RoundedCornerShape(10.dp)),
            ) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .fillMaxHeight(fillFraction)
                        .align(Alignment.BottomCenter)
                        .background(
                            when {
                                throttleValue > 0.1f -> AccentBlue
                                throttleValue < -0.1f -> AccentRed
                                else -> ButtonBorder
                            },
                            RoundedCornerShape(10.dp),
                        ),
                )
            }
            Text(
                text = "${(throttleValue * 100).roundToInt()}%",
                color = TextPrimary,
                fontSize = 11.sp,
                fontWeight = FontWeight.Bold,
            )
        }
    }
}
```

**Ajouter `SignalBars`** (après `ThrottleSlider`) :

```kotlin
@Composable
private fun SignalBars(latencyMs: Long?, modifier: Modifier = Modifier) {
    val bars = when {
        latencyMs == null  -> 0
        latencyMs < 50     -> 4
        latencyMs < 120    -> 3
        latencyMs < 250    -> 2
        else               -> 1
    }
    val color = when (bars) {
        4    -> AccentGreen
        3    -> AccentGreen
        2    -> AccentYellow
        else -> AccentRed
    }

    Row(
        modifier = modifier,
        verticalAlignment = Alignment.Bottom,
        horizontalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        (1..4).forEach { i ->
            Box(
                modifier = Modifier
                    .width(4.dp)
                    .height((4 + i * 4).dp)
                    .background(if (i <= bars) color else ButtonBorder, RoundedCornerShape(1.dp)),
            )
        }
    }
}
```

**Ajouter `BatteryGauge`** (après `SignalBars`) :

```kotlin
@Composable
private fun BatteryGauge(batteryPercent: Int?, modifier: Modifier = Modifier) {
    val color = when {
        batteryPercent == null  -> TextSecondary
        batteryPercent > 50     -> AccentGreen
        batteryPercent > 20     -> AccentYellow
        else                    -> AccentRed
    }
    val label = if (batteryPercent != null) "$batteryPercent%" else "--"

    Row(
        modifier = modifier,
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Box(
            modifier = Modifier
                .width(22.dp)
                .height(12.dp)
                .border(1.dp, color, RoundedCornerShape(2.dp))
                .padding(2.dp),
        ) {
            Box(
                modifier = Modifier
                    .fillMaxHeight()
                    .fillMaxWidth(((batteryPercent ?: 0) / 100f).coerceIn(0f, 1f))
                    .background(color, RoundedCornerShape(1.dp)),
            )
        }
        Text(label, color = color, fontSize = 10.sp, fontWeight = FontWeight.Bold)
    }
}
```

---

### Commit 12 — `feat(ui): add NoCameraOverlay and wire it in CameraViewBox`
> **Prérequis :** attendre le merge de **C3** (`CameraUiState.NoCamera` doit exister)
> **Débloque :** rien — commit terminal, peut être fait dès la vague 3 sans attendre C10/C11

**Fichier :** `app/src/main/java/com/tpi/rc_mobile/ui/CameraScreen.kt`

**Ajouter l'import `CameraUiState.NoCamera`** (il est déjà couvert par le wildcard import de `CameraUiState`).

**Modifier `CameraViewBox`** (lignes 452–457) pour gérer l'état `NoCamera` :

```kotlin
        when (cameraState) {
            CameraUiState.Idle      -> CameraOffOverlay()
            CameraUiState.Connecting -> ConnectingOverlay()
            CameraUiState.NoCamera  -> NoCameraOverlay()
            is CameraUiState.Streaming -> StreamingView(state = cameraState)
            is CameraUiState.Error   -> ErrorOverlay(message = cameraState.message, onRetry = onRetry)
        }
```

**Ajouter le composable `NoCameraOverlay`** (après `CameraOffOverlay`, avant `ConnectingOverlay`) :

```kotlin
@Composable
private fun NoCameraOverlay() {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(10.dp),
        modifier = Modifier.padding(24.dp),
    ) {
        Box(
            modifier = Modifier
                .size(72.dp)
                .background(Color(0xFF2D1010), CircleShape)
                .border(2.dp, AccentRed.copy(alpha = 0.5f), CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Box(
                modifier = Modifier
                    .size(44.dp)
                    .background(Color(0xFF3D1515), CircleShape)
                    .border(1.dp, AccentRed.copy(alpha = 0.3f), CircleShape),
                contentAlignment = Alignment.Center,
            ) {
                Box(
                    modifier = Modifier
                        .size(24.dp)
                        .background(AccentRed.copy(alpha = 0.2f), CircleShape),
                )
            }
        }
        Text(
            text = "Caméra absente",
            color = AccentRed,
            fontSize = 14.sp,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center,
        )
        Text(
            text = "Le Raspberry Pi est connecté\nmais aucune caméra n'est détectée",
            color = TextSecondary.copy(alpha = 0.6f),
            fontSize = 11.sp,
            textAlign = TextAlign.Center,
            lineHeight = 16.sp,
        )
    }
}
```

---

### Commit 13 — `feat(ui): add SignalBars and BatteryGauge to ConnectionBar`
> **Prérequis :** attendre le merge de **C9** (`latencyMs`, `batteryPercent` dans le ViewModel) + **C11** (`SignalBars` et `BatteryGauge` définis dans le fichier)
> **Débloque :** rien — dernier commit du projet

**Fichier :** `app/src/main/java/com/tpi/rc_mobile/ui/CameraScreen.kt`

**Modifier la signature de `ConnectionBar`** (lignes 349–357) pour accepter `latencyMs` et `batteryPercent` :

```kotlin
@Composable
private fun ConnectionBar(
    host: String,
    port: String,
    cameraState: CameraUiState,
    latencyMs: Long?,
    batteryPercent: Int?,
    onHostChange: (String) -> Unit,
    onPortChange: (String) -> Unit,
    onConnect: () -> Unit,
    onDisconnect: () -> Unit,
)
```

**Ajouter `SignalBars` et `BatteryGauge`** dans le `Row` de `ConnectionBar`, entre le titre "RC Camera" et le champ IP (après ligne 392, `Spacer(Modifier.width(2.dp))`) :

```kotlin
        Spacer(Modifier.weight(0.01f))
        SignalBars(latencyMs = latencyMs)
        BatteryGauge(batteryPercent = batteryPercent, modifier = Modifier.padding(start = 8.dp))
        Spacer(Modifier.width(4.dp))
```

**Mettre à jour l'appel à `ConnectionBar` dans `RcCameraScreen`** (lignes 132–140) :

```kotlin
                    ConnectionBar(
                        host           = host,
                        port           = port,
                        cameraState    = cameraState,
                        latencyMs      = latencyMs,
                        batteryPercent = batteryPercent,
                        onHostChange   = viewModel::updateHost,
                        onPortChange   = viewModel::updatePort,
                        onConnect      = viewModel::connect,
                        onDisconnect   = viewModel::disconnect,
                    )
```

---

## Résumé par développeur

| Développeur | Commits | Fichiers modifiés |
|-------------|---------|-------------------|
| **Dev 1 — Johary** | 1, 2, 3 | `DirectionRepository.kt`, `CameraViewModel.kt`, `CameraState.kt` |
| **Dev 2 — Aldo** | 4, 5 | `CameraRepository.kt` |
| **Dev 3 — Haroavo** | 6, 7 | `DirectionRepository.kt`, `CameraViewModel.kt` |
| **Dev 4 — Tantely** | 8, 9 | `CameraViewModel.kt` |
| **Dev 5 — Iaritina** | 10, 11, 12, 13 | `CameraScreen.kt` |

> **Ordre recommandé :** Dev 1 (**Johary**) en premier (corrige le bug package que tous les autres dépendent de), puis Dev 2 (**Aldo**) et Dev 3 (**Haroavo**) en parallèle, puis Dev 4 (**Tantely**) (dépend des commits 6 et 7 pour `sendThrottle`), puis Dev 5 (**Iaritina**) en dernier (dépend de tous les StateFlows ajoutés par Dev 3 et Dev 4).
