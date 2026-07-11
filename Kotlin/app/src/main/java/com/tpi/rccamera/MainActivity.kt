package com.tpi.rccamera

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import com.tpi.rccamera.camera.CameraViewModel
import com.tpi.rccamera.ui.CameraScreen

class MainActivity : ComponentActivity() {

    private val cameraViewModel: CameraViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            CameraScreen(viewModel = cameraViewModel)
        }
    }

    /**
     * Libère la connexion réseau dès que l'activité n'est plus visible.
     * Le ViewModel reste en vie ; l'utilisateur peut se reconnecter sans
     * resaisir l'adresse.
     */
    override fun onPause() {
        super.onPause()
        cameraViewModel.disconnect()
    }
}
