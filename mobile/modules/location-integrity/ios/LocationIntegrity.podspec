Pod::Spec.new do |s|
  s.name           = 'LocationIntegrity'
  s.version        = '1.0.0'
  s.summary        = 'Anti-GPS-spoofing signals and App Attest for the MCG Building Violations app'
  s.description    = 'Jailbreak / simulator / VPN / proxy signals, CoreLocation source information and Apple App Attest.'
  s.author         = 'Municipal Corporation Gurugram'
  s.homepage       = 'https://github.com/Yashjaluka2409/mcg-building-violations'
  s.license        = { :type => 'Government' }
  s.platforms      = { :ios => '15.1' }
  s.source         = { :git => '' }
  s.static_framework = true

  s.dependency 'ExpoModulesCore'
  s.frameworks = 'CoreLocation', 'DeviceCheck', 'CFNetwork'

  s.pod_target_xcconfig = { 'DEFINES_MODULE' => 'YES', 'SWIFT_COMPILATION_MODE' => 'wholemodule' }
  s.source_files = "**/*.{h,m,mm,swift,hpp,cpp}"
end
