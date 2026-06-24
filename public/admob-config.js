// Echte AdMob-Ad-Unit-IDs eintragen.
// App-IDs mit ~ gehören in Cordova beim Plugin-Install, nicht hier hinein.
window.MYAPP_ADMOB_CONFIG = {
  allowTestAds: false,
  android: {
    bannerAdUnitId: 'ca-app-pub-3947032809384601/5592032167',
    interstitialAdUnitId: 'ca-app-pub-3947032809384601/9295894913',
    rewardedAdUnitId: 'ca-app-pub-3947032809384601/1994999713'
  },
  ios: {
    bannerAdUnitId: '',
    interstitialAdUnitId: '',
    rewardedAdUnitId: ''
  }
};
