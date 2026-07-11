package com.tpi.mobile

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import com.tpi.mobile.camera.CameraViewModel
import com.tpi.mobile.ui.RcCameraScreen

class MainActivity : ComponentActivity() {

    private val cameraViewModel: CameraViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            RcCameraScreen(viewModel = cameraViewModel)
        }
    }

    /**
     * Libère la connexion réseau dès que l'activité n'est plus visible.
     * Le ViewModel (et ses champs IP/port) reste en mémoire pour la reconnexion.
     */
    override fun onPause() {
        super.onPause()
        cameraViewModel.disconnect()
    }
}
