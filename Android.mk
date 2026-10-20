# Fail normal ROM builds when vendor patch setup failed or was interrupted.
LOCAL_PATH := $(call my-dir)
ifneq ($(wildcard $(LOCAL_PATH)/.patches-failed),)
$(error Vendor patches are incomplete: $(shell cat $(LOCAL_PATH)/.patches-failed). Fix the reported patch and rerun source vendor/patches/vendorsetup.sh)
endif
