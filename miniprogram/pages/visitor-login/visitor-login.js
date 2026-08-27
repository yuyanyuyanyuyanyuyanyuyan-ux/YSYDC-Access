Page({
  data: {
    phone: '',
    password: ''
  },

  inputPhone(e) {
    this.setData({ phone: e.detail.value })
  },

  inputPassword(e) {
    this.setData({ password: e.detail.value })
  },

  login() {
    const { phone, password } = this.data
    if (!/^1[3-9]\d{9}$/.test(phone)) {
      wx.showToast({ title: '请输入正确的手机号', icon: 'none' })
      return
    }
    if (!password) {
      wx.showToast({ title: '请输入密码', icon: 'none' })
      return
    }
    wx.showLoading({ title: '登录中' })
    wx.request({
      url: 'http://127.0.0.1:8000/api/visitor/login',
      method: 'POST',
      header: { 'content-type': 'application/json' },
      data: { phone, password },
      success: (res) => {
        if (res.data.success) {
          wx.setStorageSync('user_id', res.data.user_id)
          wx.setStorageSync('visitor', res.data.user)
          wx.switchTab({ url: '/pages/visitor-home/visitor-home' })
        } else {
          wx.showToast({ title: res.data.message || '登录失败', icon: 'none' })
        }
      },
      fail: () => wx.showToast({ title: '无法连接服务器', icon: 'none' }),
      complete: () => wx.hideLoading()
    })
  },

  goRegister() {
    wx.navigateTo({ url: '/pages/register/register' })
  }
})
