const { BASE_URL } = require('../../config')

Page({

  data: {
    name: '',
    id_card: '',
    phone: '',
    password: '',
    company: ''
  },

  inputName(e) {
    this.setData({ name: e.detail.value })
  },

  inputIdCard(e) {
    this.setData({ id_card: e.detail.value })
  },

  inputPhone(e) {
    this.setData({ phone: e.detail.value })
  },

  inputPassword(e) {
    this.setData({ password: e.detail.value })
  },

  inputCompany(e) {
    this.setData({ company: e.detail.value })
  },

  submitForm() {
    const { name, id_card, phone, password, company } = this.data

    if (!name.trim()) {
      wx.showToast({ title: '请输入姓名', icon: 'none' })
      return
    }
    if (!id_card.trim()) {
      wx.showToast({ title: '请输入身份证号', icon: 'none' })
      return
    }
    if (!/^\d{17}[\dXx]$/.test(id_card.trim())) {
      wx.showToast({ title: '请输入正确的18位身份证号', icon: 'none' })
      return
    }
    if (!/^1[3-9]\d{9}$/.test(phone)) {
      wx.showToast({ title: '请输入正确的手机号', icon: 'none' })
      return
    }
    if (!password || password.length < 6) {
      wx.showToast({ title: '密码至少6位', icon: 'none' })
      return
    }

    wx.showLoading({ title: '正在注册' })

    wx.request({
      url: BASE_URL + '/api/visitor/register',
      method: 'POST',
      header: { 'content-type': 'application/json' },
      data: { name, id_card, phone, password, company },

      success: (res) => {
        if (res.data.success) {
          wx.setStorageSync('user_id', res.data.user_id)
          wx.setStorageSync('work_order_id', res.data.work_order_id)
          wx.setStorageSync('visitor', { name, phone, company })
          wx.showToast({ title: '注册成功', icon: 'success' })
          setTimeout(() => {
            wx.switchTab({ url: '/pages/visitor-home/visitor-home' })
          }, 1200)
        } else {
          wx.showToast({ title: res.data.message || '注册失败', icon: 'none' })
        }
      },

      fail: () => {
        wx.showToast({ title: '无法连接服务器', icon: 'none' })
      },

      complete: () => {
        wx.hideLoading()
      }
    })
  }
})
