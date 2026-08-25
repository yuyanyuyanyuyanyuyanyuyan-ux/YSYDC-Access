Page({

  data: {

    username: "",
    password: "",

    loading: false

  },


  // 输入账号
  inputUsername(e) {

    this.setData({
      username: e.detail.value
    })

  },


  // 输入密码
  inputPassword(e) {

    this.setData({
      password: e.detail.value
    })

  },


  // 登录
  login() {

    const {
      username,
      password
    } = this.data


    // 账号校验
    if (!username.trim()) {

      wx.showToast({
        title: "请输入管理员账号",
        icon: "none"
      })

      return
    }


    // 密码校验
    if (!password) {

      wx.showToast({
        title: "请输入管理员密码",
        icon: "none"
      })

      return
    }


    this.setData({
      loading: true
    })


    // 请求后端登录接口
    wx.request({

      url: "http://127.0.0.1:8000/api/admin/login",

      method: "POST",

      header: {
        "content-type": "application/json"
      },

      data: {
        username,
        password
      },


      success: (res) => {

        console.log("管理员登录结果：", res.data)


        if (res.data.success) {

          const admin = res.data.admin


          // 保存管理员信息
          wx.setStorageSync(
            "adminInfo",
            admin
          )


          wx.showToast({
            title: "登录成功",
            icon: "success"
          })


          // 跳转到待审批任务页面
          setTimeout(() => {

            wx.navigateTo({
              url: "/pages/admin-tasks/admin-tasks"
            })

          }, 800)

        } else {

          wx.showToast({
            title: res.data.message,
            icon: "none"
          })

        }

      },


      fail: (err) => {

        console.error(
          "管理员登录失败：",
          err
        )


        wx.showToast({
          title: "无法连接后端服务器",
          icon: "none"
        })

      },


      complete: () => {

        this.setData({
          loading: false
        })

      }

    })

  }

})